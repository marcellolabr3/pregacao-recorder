"""Watchdog de rede: garante que o Raspberry nunca fique sem acesso.

Comportamento exigido na arquitetura do projeto (itens 4, 5, 11 e 12):

    Ethernet funcional ........ opera normalmente (sem Access Point)
    Wi-Fi funcional ........... opera normalamente (sem Access Point)
    nenhum caminho por um tempo  -> ativa o Access Point de configuracao
    AP forçado pelo painel ...... fica ativo ate o administrador desligar
    Internet cai ............... painel local continua funcionando
    Tailscale cai .............. acesso local continua funcionando

Execucao: servico systemd proprio (``pregacao-netwatch.service``), usuario
normal, ``Restart=always``. Eventos sao escritos no journal do systemd com
as tags ``[NETWORK]`` e ``[TAILSCALE]``.

Todas as decisoes passam por :func:`evaluate` (funcao pura) para permitir
teste unitario sem tocar na rede real.
"""
from __future__ import annotations

import os
import signal
import time
from typing import Any, Dict, Optional

from ..config import config
from ..logging_setup import get, setup
from . import connectivity, nm, tailscale
from .nm import MSG_AP_ACTIVE, MSG_AP_STARTING, MSG_AP_STOPPING, MSG_WIFI_FAILED

log = get("network")

# segundos sem NENHUM caminho de rede antes de subir o Access Point
AP_AFTER_WIFI_FAIL = 45   # ha rede salva tentando reconectar
AP_AFTER_NO_NETWORK = 12  # nada configurado (instalacao nova)

# mensagens de transicao (formato pedido na documentacao do projeto).
# As mensagens do Access Point sao registradas em nm.py (dono da acao).
MSG_ETHERNET_ON = "[NETWORK] Ethernet connected"
MSG_ETHERNET_OFF = "[NETWORK] Ethernet disconnected"
MSG_WIFI_ON = "[NETWORK] Wi-Fi connected: {ssid}"
MSG_WIFI_OFF = "[NETWORK] Wi-Fi disconnected"
MSG_INET_ON = "[NETWORK] Internet available"
MSG_INET_OFF = "[NETWORK] Internet unavailable"
MSG_TS_ON = "[TAILSCALE] Connected"
MSG_TS_OFF = "[TAILSCALE] Disconnected"


def evaluate(*,
             eth_connected: bool,
             wifi_connected: bool,
             ap_active: bool,
             ap_forced: bool,
             seconds_degraded: float,
             has_saved_wifi: bool,
             grace: Optional[float] = None,
             ) -> str:
    """Decide o proximo passo do Access Point.

    Devolve ``"keep"`` (nada a fazer), ``"ap_on"`` ou ``"ap_off"``.

    ``grace`` e o tempo minimo sem rede antes de subir o AP; quando nao for
    informado, usa 45 s se existe rede salva e 12 s se nao existe.
    """
    if grace is None:
        grace = AP_AFTER_WIFI_FAIL if has_saved_wifi else AP_AFTER_NO_NETWORK

    if ap_forced:
        return "keep" if ap_active else "ap_on"

    if eth_connected or wifi_connected:
        # ha caminho de acesso funcional: o AP deixa de ser necessario
        return "ap_off" if ap_active else "keep"

    if ap_active:
        # ja estamos no modo de recuperacao; nada a fazer
        return "keep"

    if seconds_degraded >= grace:
        return "ap_on"
    return "keep"


class Watchdog:
    def __init__(self, interval: float = 15.0,
                 test_mode: str = "normal") -> None:
        self.interval = max(5.0, float(interval))
        self.test_mode = test_mode  # normal | offline | online (validacao)
        self._stop = False
        self._degraded_since: Optional[float] = None
        self._last: Dict[str, Any] = {}

    # -- utilitarios ----------------------------------------------------
    def _changed(self, key: str, value: Any) -> bool:
        """Registra uma transicao; devolve True apenas na primeira vez."""
        if self._last.get(key) == value:
            return False
        self._last[key] = value
        return True

    def _reload_config(self) -> None:
        try:
            config.reload()
        except Exception as exc:  # pragma: no cover - defesa do daemon
            log.warning("[NETWORK] falha ao reler configuracao: %s", exc)

    # -- um ciclo -------------------------------------------------------
    def cycle(self) -> Dict[str, Any]:
        self._reload_config()

        try:
            eth = nm.ethernet_status()
        except Exception as exc:
            log.warning("[NETWORK] Ethernet read failed: %s", exc)
            eth = {"connected": False}
        try:
            wifi = nm.wifi_status()
        except Exception as exc:
            log.warning("[NETWORK] Wi-Fi read failed: %s", exc)
            wifi = {"connected": False, "ssid": ""}
        try:
            ap = nm.ap_status()
        except Exception as exc:
            log.warning("[NETWORK] AP read failed: %s", exc)
            ap = {"active": False}
        saved = nm.saved_wifi()

        eth_on = bool(eth.get("connected"))
        wifi_on = bool(wifi.get("connected"))
        ap_on = bool(ap.get("active"))

        # ---- logs de transicao ----
        if self.test_mode == "offline":
            eth_on = wifi_on = False
        if self._changed("eth", eth_on):
            log.info(MSG_ETHERNET_ON if eth_on else MSG_ETHERNET_OFF)
        if self._changed("wifi", wifi_on):
            if wifi_on:
                # .format e proposital: a mensagem ja chega pronta e um "%"
                # dentro do SSID nao pode quebrar a formatacao do logging.
                log.info(MSG_WIFI_ON.format(ssid=wifi.get("ssid") or "?"))
            else:
                log.info(MSG_WIFI_OFF)

        local = eth_on or wifi_on

        # ---- Internet (so quando ha caminho local) ----
        internet: Dict[str, Any] = {"connected": False}
        if local:
            try:
                internet = connectivity.check(timeout=3.0)
            except Exception as exc:  # pragma: no cover - defesa do daemon
                log.warning("[NETWORK] Internet test failed: %s", exc)
        if self._changed("internet", bool(internet.get("connected"))):
            log.info(MSG_INET_ON if internet.get("connected") else MSG_INET_OFF)

        # ---- Tailscale (acesso remoto nunca e obrigatorio) ----
        try:
            ts = tailscale.status()
        except Exception as exc:  # pragma: no cover - defesa do daemon
            log.warning("[TAILSCALE] status failed: %s", exc)
            ts = {"connected": False}
        if self._changed("tailscale", bool(ts.get("connected"))):
            log.info(MSG_TS_ON if ts.get("connected") else MSG_TS_OFF)

        # ---- temporizacao da degradacao ----
        if local:
            self._degraded_since = None
            degraded_for = 0.0
        else:
            now = time.monotonic()
            if self._degraded_since is None:
                self._degraded_since = now
            degraded_for = now - self._degraded_since

        # A flag do modo de configuracao e lida AQUI, por ultimo: entre a
        # primeira leitura e a acao passam varios segundos de testes de rede, e
        # o administrador pode ter ligado (ou desligado) o modo pelo celular
        # nesse meio-tempo. Com a leitura atrasada o AP recem-ligado nao e
        # derrubado nem o recem-desligado e religado na mesma volta.
        forced = bool(config.get("network.ap_forced", False))

        action = evaluate(
            eth_connected=eth_on,
            wifi_connected=wifi_on,
            ap_active=ap_on,
            ap_forced=forced,
            seconds_degraded=degraded_for,
            has_saved_wifi=bool(saved),
        )

        error: str = ""
        if action == "ap_on":
            if not ap_on and saved:
                # ha rede salva que nao conectou: registra a falha antes do AP
                log.info(MSG_WIFI_FAILED)
            try:
                nm.ap_enable()   # nm.py registra Starting/Configuration AP active
                ap_on = True
            except nm.NetworkError as exc:
                error = str(exc)
                log.error("[NETWORK] AP start failed: %s", exc)
                # tenta de novo no proximo ciclo (o servico systemd cobre os
                # casos fatais; aqui a repeticao e temporal)
        elif action == "ap_off":
            try:
                nm.ap_disable()  # nm.py registra Stopping configuration AP
                ap_on = False
            except nm.NetworkError as exc:
                error = str(exc)
                log.error("[NETWORK] AP stop failed: %s", exc)

        return {
            "action": action,
            "ethernet": eth_on,
            "wifi": wifi_on,
            "ssid": wifi.get("ssid") if wifi_on else "",
            "internet": bool(internet.get("connected")),
            "ap": ap_on,
            "ap_forced": forced,
            "tailscale": bool(ts.get("connected")),
            "degraded_for": round(degraded_for, 1),
            "error": error,
        }

    # -- loop principal -------------------------------------------------
    def run(self) -> None:
        log.info("[NETWORK] watchdog iniciado (intervalo=%.0fs)",
                 self.interval)
        while not self._stop:
            started = time.monotonic()
            try:
                self.cycle()
            except Exception as exc:  # pragma: no cover - defesa do daemon
                log.exception("[NETWORK] ciclo falhou: %s", exc)
            elapsed = time.monotonic() - started
            wait = max(1.0, self.interval - elapsed)
            deadline = time.monotonic() + wait
            while not self._stop and time.monotonic() < deadline:
                time.sleep(0.5)
        log.info("[NETWORK] watchdog encerrado")

    def stop(self, *_args) -> None:
        self._stop = True


def main(argv: Optional[list] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="pregacao-netwatch")
    parser.add_argument("--interval", type=float, default=None,
                        help="segundos entre ciclos (padrao 15)")
    parser.add_argument("--once", action="store_true",
                        help="executa um unico ciclo e sai (diagnostico)")
    parser.add_argument("--test-mode", default=os.environ.get(
        "PREGACAO_NETWATCH_TEST", "normal"),
        help="normal | offline | online (validacao sem tocar na rede)")
    args = parser.parse_args(argv)

    setup()
    interval = args.interval or float(
        os.environ.get("PREGACAO_NETWATCH_INTERVAL", "15"))

    wd = Watchdog(interval=interval, test_mode=args.test_mode)
    if args.once:
        result = wd.cycle()
        print(result)
        return 0

    signal.signal(signal.SIGTERM, wd.stop)
    signal.signal(signal.SIGINT, wd.stop)
    wd.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
