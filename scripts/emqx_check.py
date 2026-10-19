"""Validador ao vivo do controle remoto (ciclo ponta a ponta na EMQX).

Simula o APK: conecta no broker, le as mensagens retidas (avail + state) e
executa STATUS -> START -> START (precisa ser idempotente) -> STOP, imprimindo
o ack de cada um. Sai com codigo != 0 se algo falhar.

Credenciais NUNCA ficam aqui: sao lidas do ambiente ou de um arquivo .env
(por padrao .env na raiz do projeto).

Uso:
    python scripts/emqx_check.py                 # ciclo completo
    python scripts/emqx_check.py STATUS           # so um comando
    python scripts/emqx_check.py --env /caminho/.env
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import os
import ssl
import sys
import time

DEFAULT_ENV = str(Path(__file__).resolve().parent.parent / ".env")


def load_env(path: str) -> None:
    """Carrega KEY=VALUE simples sem sobrescrever o que ja esta no ambiente."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(name: str, default: str = "") -> str:
    return str(os.environ.get(name, "") or default).strip()


class Validador:
    def __init__(self, device_id: str, host: str, port: int, user: str,
                 password: str, tls: bool) -> None:
        import paho.mqtt.client as mqtt

        self.topics = {
            "root": f"pregacao/{device_id}",
            "avail": f"pregacao/{device_id}/avail",
            "state": f"pregacao/{device_id}/state",
            "ack": f"pregacao/{device_id}/ack",
            "cmd": f"pregacao/{device_id}/cmd",
        }
        self.retained: dict = {}
        self.acks: list = []
        self.granted = None
        self.connected_rc: int = -1
        self.host, self.port, self.tls = host, port, tls

        try:
            from paho.mqtt.enums import CallbackAPIVersion
            client = mqtt.Client(
                callback_api_version=CallbackAPIVersion.VERSION2,
                client_id=f"validador-{device_id}",
            )
        except Exception:
            client = mqtt.Client(client_id=f"validador-{device_id}")

        if user:
            client.username_pw_set(user, password)
        if tls:
            try:
                client.tls_set()
            except Exception as exc:  # CA do sistema indisponivel
                print(f"  [aviso] TLS com certificado padrao falhou ({exc}); "
                      "tentando sem validacao (so diagnostico)")
                client.tls_set(cert_reqs=ssl.CERT_NONE)
                client.tls_insecure_set(True)
        client.on_connect = self._on_connect
        client.on_subscribe = self._on_subscribe
        client.on_message = self._on_message
        self.client = client

    # -- callbacks -------------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, *extra):
        rc = int(getattr(reason_code, "value", reason_code))
        self.connected_rc = rc
        print(f"  on_connect rc={rc}")
        if rc == 0:
            client.subscribe(self.topics["root"] + "/#", qos=1)

    def _on_subscribe(self, client, userdata, mid, granted_qos, *extra):
        self.granted = granted_qos
        print(f"  subscribe concedido: {granted_qos}")

    def _on_message(self, client, userdata, message):
        text = message.payload.decode("utf-8", "replace")
        tag = " RETIDO" if message.retain else ""
        print(f"  <{message.topic}>{tag} {text[:400]}")
        if message.retain:
            self.retained[message.topic] = text
        if message.topic.endswith("/ack"):
            self.acks.append(text)

    # -- utilidades ------------------------------------------------------
    def conectar(self, timeout: float = 15.0) -> bool:
        self.client.connect(self.host, self.port, 60)
        self.client.loop_start()
        deadline = time.time() + timeout
        while time.time() < deadline and self.connected_rc != 0:
            time.sleep(0.3)
        time.sleep(4)  # deixa as mensagens retidas chegarem
        return self.connected_rc == 0

    def enviar(self, cmd: str, req_id: str, timeout: float = 20.0) -> dict | None:
        payload = json.dumps({"cmd": cmd, "req_id": req_id})
        print(f"  -> cmd {cmd} ({payload})")
        self.client.publish(self.topics["cmd"], payload, qos=1)
        deadline = time.time() + timeout
        while time.time() < deadline:
            for raw in list(self.acks):
                try:
                    ack = json.loads(raw)
                except ValueError:
                    continue
                if ack.get("req_id") == req_id:
                    self.acks.remove(raw)
                    print("  <- ack: " + json.dumps(ack, ensure_ascii=False))
                    return ack
            time.sleep(0.3)
        print(f"  !! sem ack para {req_id} em {int(timeout)}s")
        return None

    def fechar(self) -> None:
        self.client.loop_stop()
        try:
            self.client.disconnect()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida o controle remoto")
    parser.add_argument("comando", nargs="?", default="",
                        help="START, STOP ou STATUS (vazio = ciclo completo)")
    parser.add_argument("--env", default=DEFAULT_ENV,
                        help=f"arquivo .env (padrao: {DEFAULT_ENV})")
    parser.add_argument("--insecure", action="store_true",
                        help="nao valida o certificado TLS (diagnostico)")
    args = parser.parse_args()

    load_env(args.env)

    host = env("PREGACAO_REMOTE_HOST")
    if not host:
        print(f"FALHA: PREGACAO_REMOTE_HOST vazio (procurei em {args.env})")
        return 2

    port = int(env("PREGACAO_REMOTE_PORT", "8883"))
    tls = env("PREGACAO_REMOTE_TLS", "1") not in ("0", "false", "no", "off")
    device = env("PREGACAO_DEVICE_ID", "pregacao-igreja-01")
    user = env("PREGACAO_REMOTE_USERNAME") or device
    password = env("PREGACAO_REMOTE_PASSWORD")

    print(f"== conectando em {host}:{port} (device_id={device}) ==")
    val = Validador(device, host, port, user, password, tls)
    if args.insecure:
        val.client.tls_set(cert_reqs=ssl.CERT_NONE)
        val.client.tls_insecure_set(True)
    if not val.conectar():
        print(f"FALHA: nao conectou (rc={val.connected_rc})")
        val.fechar()
        return 1

    if val.granted and val.granted[0] == 128:
        print("FALHA: subscribe negado pelo broker (code 128)")
        val.fechar()
        return 1

    print("== mensagens retidas ==")
    for topic in sorted(val.retained):
        print(f"  {topic} = {val.retained[topic][:300]}")

    falhas = 0
    if args.comando:
        print(f"== comando {args.comando} ==")
        if val.enviar(args.comando.upper(), "req-1") is None:
            falhas += 1
    else:
        print("== ciclo completo ==")
        for cmd, req in (("STATUS", "s1"), ("START", "s2"),
                         ("START", "s3"), ("STOP", "s4")):
            if cmd == "START" and req == "s3":
                print("-- segundo START (precisa ser idempotente) --")
            if val.enviar(cmd, req) is None:
                falhas += 1
            time.sleep(1)

    time.sleep(2)
    print("== estado final retido ==")
    print("  " + val.retained.get(val.topics["state"], "(sem state retido)")[:600])
    val.fechar()
    print("RESULTADO: " + ("FALHAS" if falhas else "ok"))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
