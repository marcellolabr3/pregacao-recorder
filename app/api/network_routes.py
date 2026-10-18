"""Endpoints de rede (painel CONFIGURACOES -> REDE).

Separacao de responsabilidades:

    web-panel   -> este arquivo (I/O HTTP, validacao, autenticacao)
    network-*   -> app/network/* (nmcli, tailscale, conectividade)

Protecao:

    leitura  -> PIN comum (require_auth)   : status, teste de conexao
    alteracao-> PIN de administrador       : conectar/forget/AP/tailscale

Nenhuma rota devolve senha Wi-Fi, senha de AP ou credencial.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional, Tuple

from flask import jsonify, request

from .. import notify
from ..config import config
from ..logging_setup import get
from ..network import connectivity, nm, tailscale
from ..network.status import build as build_status
from . import auth

log = get("api")

# uma operacao de rede por vez: conectar enquanto o AP sobe causa corrida
_lock = threading.Lock()
_cache: Dict[str, Any] = {"ts": 0.0, "data": None}
CACHE_SECONDS = 4.0


def _err(message: str, status: int = 400, code: str = "erro"):
    return jsonify({"error": code, "message": message}), status


def _body() -> Dict[str, Any]:
    raw = request.get_json(silent=True)
    return raw if isinstance(raw, dict) else {}


def _bust() -> None:
    """Invalida o cache de status.

    Nao usa ``_lock``: esta funcao e chamada dentro de operacoes que ja
    seguram o lock (e ``threading.Lock`` nao e reentrante). A atribuicao de
    dois campos e atomica em Python, entao basta limpar direto.
    """
    _cache["data"] = None
    _cache["ts"] = 0.0


def network_status_payload(refresh: bool = False) -> Dict[str, Any]:
    now = time.monotonic()
    if not refresh and _cache["data"] and now - _cache["ts"] < CACHE_SECONDS:
        return _cache["data"]
    data = build_status()
    _cache["data"] = data
    _cache["ts"] = time.monotonic()
    return data


def register_network_routes(app) -> None:
    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    @app.get("/api/network/status")
    @auth.require_auth
    def network_status():
        refresh = request.args.get("refresh", "") in ("1", "true", "yes")
        try:
            return jsonify(network_status_payload(refresh=refresh))
        except Exception as exc:  # pragma: no cover - defesa de UI
            log.warning("[NETWORK] status falhou: %s", exc)
            return _err(f"falha ao ler a rede: {exc}", 500, "status_falhou")

    @app.post("/api/network/connectivity-test")
    @auth.require_auth
    def connectivity_test():
        started = time.monotonic()
        result = connectivity.check(timeout=4.0)
        result["seconds"] = round(time.monotonic() - started, 2)
        result["local"] = bool(
            nm.ethernet_status().get("connected")
            or nm.wifi_status().get("connected")
        )
        log.info("[NETWORK] connectivity test: internet=%s local=%s",
                 result["connected"], result["local"])
        return jsonify(result)

    # ------------------------------------------------------------------
    # Wi-Fi
    # ------------------------------------------------------------------
    @app.get("/api/network/wifi/scan")
    @auth.require_admin
    def wifi_scan():
        rescan = request.args.get("rescan", "1") in ("1", "true", "yes")
        if not nm.nmcli_available():
            return _err("NetworkManager indisponivel neste sistema", 501,
                        "sem_networkmanager")
        networks = nm.scan(rescan=rescan)
        return jsonify({
            "networks": networks,
            "count": len(networks),
            "device": nm.wifi_device(),
            "enabled": nm.wifi_enabled(),
        })

    @app.post("/api/network/wifi/connect")
    @auth.require_admin
    def wifi_connect():
        body = _body()
        ssid = str(body.get("ssid") or "").strip()
        password = body.get("password")
        password = str(password) if password else None
        if not ssid:
            return _err("Selecione uma rede Wi-Fi")
        if not nm.nmcli_available():
            return _err("NetworkManager indisponivel neste sistema", 501,
                        "sem_networkmanager")

        if not _lock.acquire(blocking=False):
            return _err("Outra operacao de rede em andamento; tente de novo em "
                        "poucos segundos", 409, "ocupado")
        try:
            ap_active = nm.ap_status()["active"]
            current = nm.wifi_status()
            if current.get("connected") and current.get("ssid") != ssid:
                log.info("[NETWORK] Switching Wi-Fi network: %s -> %s",
                         current.get("ssid"), ssid)
            if ap_active:
                # o radio nao faz AP e cliente ao mesmo tempo: baixa o AP,
                # conecta e, se falhar, o AP volta (o usuario nao fica sem acesso)
                log.info("[NETWORK] Desativando Access Point para conectar ao Wi-Fi")
                try:
                    nm.ap_disable()
                except nm.NetworkError as exc:
                    return _err(f"nao foi possivel desligar o Access Point: {exc}",
                                409, "ap_ocupado")
            try:
                nm.connect(ssid, password)
            except nm.NetworkError as exc:
                if ap_active:
                    _restore_ap("falha ao conectar no Wi-Fi")
                return _err(str(exc), 409, "wifi_falhou")
            if ap_active:
                config.set("network.ap_forced", False)
                config.save()
            _bust()
            notify.notify("rede", f"Wi-Fi conectado: {ssid}", level="success")
            return jsonify({
                "ok": True,
                "ssid": ssid,
                "ap_was_active": ap_active,
                "ap_disabled": ap_active,
                "message": ("Access Point desativado; entre na rede "
                            f"'{ssid}' com o celular para voltar ao painel"
                            if ap_active else "conectado"),
                "status": network_status_payload(refresh=True),
            })
        finally:
            _lock.release()

    @app.post("/api/network/wifi/disconnect")
    @auth.require_admin
    def wifi_disconnect():
        if not _lock.acquire(blocking=False):
            return _err("Outra operacao de rede em andamento", 409, "ocupado")
        try:
            nm.disconnect()
        except nm.NetworkError as exc:
            return _err(str(exc), 409, "wifi_falhou")
        finally:
            _lock.release()
        _bust()
        notify.notify("rede", "Wi-Fi desconectado", level="warning")
        return jsonify({"ok": True, "status": network_status_payload(refresh=True)})

    @app.post("/api/network/wifi/forget")
    @auth.require_admin
    def wifi_forget():
        ssid = str(_body().get("ssid") or "").strip()
        if not ssid:
            return _err("Informe a rede a esquecer")
        if not _lock.acquire(blocking=False):
            return _err("Outra operacao de rede em andamento", 409, "ocupado")
        try:
            nm.forget(ssid)
        except nm.NetworkError as exc:
            return _err(str(exc), 409, "esquecer_falhou")
        finally:
            _lock.release()
        _bust()
        notify.notify("rede", f"Rede esquecida: {ssid}", level="info")
        return jsonify({"ok": True, "ssid": ssid,
                        "status": network_status_payload(refresh=True)})

    @app.get("/api/network/wifi/saved")
    @auth.require_admin
    def wifi_saved():
        return jsonify({"saved": nm.saved_wifi()})

    # ------------------------------------------------------------------
    # Access Point de configuracao
    # ------------------------------------------------------------------
    @app.post("/api/network/ap/enable")
    @auth.require_admin
    def ap_enable():
        if not _lock.acquire(blocking=False):
            return _err("Outra operacao de rede em andamento", 409, "ocupado")
        try:
            # persiste a intencao: se o sistema reiniciar, o watchdog mantem o AP
            config.set("network.ap_forced", True)
            config.save()
            try:
                nm.ap_enable()
            except nm.NetworkError as exc:
                config.set("network.ap_forced", False)
                config.save()
                return _err(str(exc), 409, "ap_falhou")
        finally:
            _lock.release()
        _bust()
        notify.notify("rede", "Modo de configuracao Wi-Fi ativado", level="warning")
        log.info("[NETWORK] Modo de configuracao Wi-Fi ativado pelo painel")
        return jsonify({"ok": True, "status": network_status_payload(refresh=True)})

    @app.post("/api/network/ap/disable")
    @auth.require_admin
    def ap_disable():
        if not _lock.acquire(blocking=False):
            return _err("Outra operacao de rede em andamento", 409, "ocupado")
        try:
            config.set("network.ap_forced", False)
            config.save()
            try:
                nm.ap_disable()
            except nm.NetworkError as exc:
                return _err(str(exc), 409, "ap_falhou")
        finally:
            _lock.release()
        _bust()
        notify.notify("rede", "Modo de configuracao Wi-Fi desativado",
                      level="info")
        return jsonify({"ok": True, "status": network_status_payload(refresh=True)})

    # ------------------------------------------------------------------
    # Tailscale (acesso remoto)
    # ------------------------------------------------------------------
    @app.get("/api/network/tailscale/status")
    @auth.require_auth
    def tailscale_status():
        return jsonify(tailscale.status())

    @app.post("/api/network/tailscale/login")
    @auth.require_admin
    def tailscale_login():
        try:
            result = tailscale.start_login()
        except Exception as exc:  # pragma: no cover - defesa de UI
            log.warning("[TAILSCALE] login falhou: %s", exc)
            return _err(f"nao foi possivel iniciar a autenticacao: {exc}",
                        500, "tailscale_falhou")
        if result.get("started"):
            log.info("[TAILSCALE] autenticacao iniciada pelo painel")
        return jsonify(result)

    @app.post("/api/network/tailscale/test")
    @auth.require_admin
    def tailscale_test():
        info = tailscale.status()
        remote_ok = bool(info.get("connected") and info.get("ip"))
        return jsonify({
            "ok": remote_ok,
            "connected": info.get("connected"),
            "ip": info.get("ip"),
            "hostname": info.get("hostname"),
            "message": (f"acesso remoto disponivel em "
                        f"http://{info.get('ip')}:{config.port}"
                        if remote_ok else (info.get("message")
                                           or "Tailscale desconectado")),
        })


def _restore_ap(reason: str) -> None:
    """Volta o Access Point apos uma falha: o usuario nunca fica sem acesso."""
    try:
        nm.ap_enable()
        log.info("[NETWORK] Access Point restaurado apos %s", reason)
    except nm.NetworkError as exc:
        log.error("[NETWORK] falha ao restaurar o Access Point (%s): %s",
                  reason, exc)
