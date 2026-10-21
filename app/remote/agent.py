"""Remote Agent - ponte entre o equipamento e o servico de comunicacao remoto.

Fluxo (roteiro, secoes 4 e 5):

    APK Android <--Internet--> servico remoto <--MQTT/TLS (conexao de saida)--> AGENTE
                                                                                   |
                                                                             HTTP localhost
                                                                                   v
                                                                              RECORDER -> SSD

Decisoes importantes:

* O agente e um processo SEPARADO, iniciado pelo ``iniciar-tudo.bat``. Se ele cair,
  a gravacao, a recuperacao de quedas e o upload continuam: o controle remoto
  NUNCA e requisito para gravar.
* Toda conexao sai do PC (NAT amigavel): nao ha port forwarding, IP
  publico, DDNS nem abertura no roteador da igreja.
* Os comandos sao executados na API LOCAL ja existente (``/api/start``,
  ``/api/stop``), que ja garante uma unica gravacao por vez (HTTP 409) e ja
  trata finalizacao, fila de upload e recuperacao.
* O agente nao toca em audio: transporta apenas comandos, autenticacao,
  estados e informacoes de controle (o audio nunca passa pelo servico remoto).

Protocolo (tudo sob ``pregacao/<device_id>/``):

    cmd     APK -> agente    {"cmd":"START|STOP|STATUS","req_id":"..."}
    ack     agente -> APK    resposta ao req_id (ok, estado, erro)
    state   agente -> APK    estado completo (RETIDO: quem conectar ja ve)
    events  agente -> APK    eventos do sistema (gravacao_*, upload_*)
    avail   agente -> APK    "online"/"offline" (retido + LWT)
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import signal
import threading
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from .. import paths
from ..config import config, load_env, sanitize_device_id
from ..logging_setup import get, setup as setup_logging
from ..states import State

log = get("remote")

try:  # dependencia opcional: sem ela o agente apenas nao sobe
    import paho.mqtt.client as mqtt
except Exception:  # pragma: no cover - instalado pelo requirements.txt
    mqtt = None  # type: ignore[assignment]

TOPIC_ROOT = "pregacao"
ONLINE = "online"
OFFLINE = "offline"
COMMANDS = (
    "START", "STOP", "CANCEL", "STATUS",
    # espelho do painel: conta Google e destino de gravacao
    "DRIVE_STATUS", "DRIVE_CONNECT", "DRIVE_FINISH",
    "DRIVE_DISCONNECT", "DRIVE_TEST",
    "STORAGE_LIST", "STORAGE_SET",
    "PREGACAO_LISTAR", "PREGACAO_OBTER", "PREGACAO_CRIAR",
    "PREGACAO_ATUALIZAR", "PREGACAO_DELETAR",
)

# Prazo de validade de um comando (secao 5 do roteiro do MVP): o remetente
# envia o campo "ts" (epoch segundos) junto do req_id e o agente recusa
# mensagens alem deste desvio - um comando atrasado (fila parada, reenvio
# tardio) NAO pode executar depois que a situacao mudou. O desvio cobre a
# diferenca de relogio entre celular e PC (ambos sincronizam por NTP;
# 120 s e folgado). Comandos sem "ts" (APK Kotlin antigo) continuam aceitos.
COMANDO_TTL_SEGUNDOS = 120

# Argumentos de autorizacao Google e destino de gravacao; nunca senha de rede.
ARGS = (
    "code", "state", "path", "id", "versao", "data", "horario",
    "pregador", "igreja", "texto_base", "tema", "offset",
)
PREGACAO_CAMPOS = ("data", "horario", "pregador", "igreja", "texto_base", "tema")

# Cabecalho que marca TODAS as chamadas do agente a API local: o painel
# registra a "ultima vista" e o /api/integracoes so declara o EMQX
# conectado enquanto o agente estiver batendo de verdade (nada simulado).
CABECALHO_AGENTE = "X-Pregacao-Agent"
VERSAO_AGENTE = "1"

# valores de PREGACAO_REMOTE_ENABLED que desligam o agente por expressao
_DISABLED_VALUES = {"0", "false", "no", "off", "desligado"}


# ======================================================================
# utilitarios puros (facilmente testaveis sem rede)
# ======================================================================
def _env_int(env: Dict[str, str], name: str, default: int) -> int:
    try:
        return int(str(env.get(name, "") or default).strip())
    except (TypeError, ValueError):
        return default


def _env_bool(env: Dict[str, str], name: str, default: bool) -> bool:
    raw = str(env.get(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def topics(device_id: str) -> Dict[str, str]:
    """Monta todos os topics do aparelho a partir do device_id."""
    base = f"{TOPIC_ROOT}/{device_id}"
    return {
        "root": base,
        "avail": f"{base}/avail",
        "state": f"{base}/state",
        "events": f"{base}/events",
        # progresso do estudo por job (S3): payload pequeno, RETIDO - o
        # celular que reconectar recebe o estado atual sem reiniciar nada
        "jobs": f"{base}/jobs",
        "ack": f"{base}/ack",
        "cmd": f"{base}/cmd",
    }


def project_status(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Reduz o payload completo da API ao que o APK precisa (e ao que cabe
    numa mensagem). O cronometro e calculado pelo APK a partir de
    ``started_at``, entao a duracao nao precisa ser republicada a cada segundo.
    """
    recording = snapshot.get("recording") or {}
    uploads = snapshot.get("uploads") or {}
    storage = snapshot.get("storage") or {}
    drive = snapshot.get("drive") or {}
    network = snapshot.get("network") or {}
    recovery = snapshot.get("recovery") or []
    return {
        "device_id": snapshot.get("device_id"),
        "device_name": snapshot.get("device_name"),
        "state": snapshot.get("state"),
        "banner": snapshot.get("banner"),
        "detail": snapshot.get("detail"),
        "session_id": snapshot.get("session_id"),
        "started_at": snapshot.get("started_at"),
        "recording": {
            "active": bool(recording.get("active")),
            "segments": int(recording.get("segments") or 0),
            "bytes": int(recording.get("bytes") or 0),
            "duration": float(recording.get("duration") or 0),
        },
        "uploads": {
            "pending": int(uploads.get("pending") or 0),
            "running": int(uploads.get("running") or 0),
            "done": int(uploads.get("done") or 0),
            "failed": int(uploads.get("failed") or 0),
        },
        "drive_connected": bool(drive.get("connected")),
        "network_online": bool(network.get("online")),
        # Destino configurado e aviso caso o volume nao esteja disponivel.
        "recording_dir": str(snapshot.get("recording_dir") or ""),
        "storage_aviso": str(snapshot.get("storage_aviso") or ""),
        "free_mb": int(storage.get("free_mb") or 0),
        "recovery_pending": len(recovery),
        "ts": time.time(),
    }


def signature(payload: Dict[str, Any]) -> str:
    """Assinatura do estado: so muda quando ha algo novo a comunicar.

    Sem ela o agente republicaria a mensagem de estado a cada ciclo mesmo
    sem mudanca (gastando cota do servico remoto e enxando o APK).
    """
    recording = payload.get("recording") or {}
    uploads = payload.get("uploads") or {}
    return "|".join(
        str(part)
        for part in (
            payload.get("state"),
            payload.get("banner"),
            payload.get("session_id"),
            payload.get("started_at"),
            recording.get("active"),
            recording.get("segments"),
            uploads.get("pending"),
            uploads.get("running"),
            uploads.get("done"),
            uploads.get("failed"),
            payload.get("drive_connected"),
            payload.get("recovery_pending"),
            payload.get("api_ok"),
            payload.get("recording_dir"),
            payload.get("storage_aviso"),
        )
    )


def parse_command(raw: Any) -> Dict[str, Any]:
    """Normaliza o que chegou no topic ``cmd``.

    Aceita o texto puro (``"START"``) ou o objeto JSON
    (``{"cmd":"START","req_id":"abc"}``). Devolve
    ``{"cmd": ..., "req_id": ...}`` ou ``{"error": ...}``.
    """
    if isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw).decode("utf-8", "replace")
    text = str(raw or "").strip()
    if not text:
        return {"error": "comando vazio"}
    if len(text) > 4096:
        return {"error": "comando muito longo"}

    payload: Dict[str, Any] = {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            return {"error": "json invalido"}
        if not isinstance(data, dict):
            return {"error": "payload invalido"}
        payload = data

    cmd = str(payload.get("cmd") or text).strip().upper()
    if cmd not in COMMANDS:
        return {"error": f"comando desconhecido: {cmd}"}
    out: Dict[str, Any] = {"cmd": cmd, "req_id": str(payload.get("req_id") or "")}
    for campo in ARGS:
        valor = payload.get(campo)
        if valor is None or not str(valor).strip():
            continue
        out[campo] = str(valor)
    # prazo de validade: "ts" e o epoch (segundos) gravado pelo remetente no
    # envio. Alem do desvio permitido o comando e recusado ANTES de tocar na
    # API local - e o ack leva cmd/req_id para o aplicativo saber de qual
    # pedido veio a recusa.
    ts = payload.get("ts")
    if ts is not None and str(ts).strip():
        try:
            quando = float(ts)
        except (TypeError, ValueError):
            quando = None
        if quando is not None and abs(time.time() - quando) > COMANDO_TTL_SEGUNDOS:
            return {
                "error": "comando expirado (prazo de validade de "
                         f"{COMANDO_TTL_SEGUNDOS}s)",
                "cmd": cmd,
                "req_id": out["req_id"],
            }
    return out


def iter_sse(lines: Iterable[str]) -> Iterator[Dict[str, str]]:
    """Converte linhas de um fluxo SSE em ``{"event":..., "data":...}``.

    Reproduz o formato de ``/api/stream``: blocos separados por linha vazia,
    campos ``event:``/``data:`` e comentarios ``: keep-alive`` ignorados.
    """
    event = ""
    data: List[str] = []
    for raw in lines:
        line = str(raw).rstrip("\r\n")
        if line.startswith(":"):
            continue
        if not line:
            if event or data:
                yield {"event": event, "data": "\n".join(data)}
            event, data = "", []
            continue
        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data.append(line[len("data:"):].strip())
    if event or data:
        yield {"event": event, "data": "\n".join(data)}


def parse_event(event: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Converte um bloco SSE (que nao seja ``status``) em payload de evento."""
    try:
        data = json.loads(event.get("data") or "{}")
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "kind": data.get("kind"),
        "seq": data.get("seq"),
        "ts": data.get("ts"),
        "data": data.get("data") or {},
    }


# ======================================================================
# configuracao local (CONFIG tem precedencia sobre o .env legado)
# ======================================================================
class RemoteSettings:
    """Configuracao salva em CONFIG, com fallback para o ambiente (``.env``)."""

    def __init__(self, environ: Optional[Dict[str, str]] = None) -> None:
        if environ is None:
            from .settings import effective_environment
            env = effective_environment(config, os.environ)
        else:
            env = dict(environ)
        self.host = str(env.get("PREGACAO_REMOTE_HOST", "") or "").strip()
        self.port = _env_int(env, "PREGACAO_REMOTE_PORT", 8883)
        self.tls = _env_bool(env, "PREGACAO_REMOTE_TLS", True)
        self.username = str(env.get("PREGACAO_REMOTE_USERNAME", "") or "").strip()
        self.password = str(env.get("PREGACAO_REMOTE_PASSWORD", "") or "")
        self.interval = max(2, _env_int(env, "PREGACAO_REMOTE_INTERVAL", 10))
        self.keepalive = max(10, _env_int(env, "PREGACAO_REMOTE_KEEPALIVE", 60))
        self.enabled_flag = str(env.get("PREGACAO_REMOTE_ENABLED", "auto") or "auto").strip()
        self.api_base = (
            str(env.get("PREGACAO_API_BASE", "") or "").strip()
            or f"http://127.0.0.1:{config.port}"
        )
        self.pin = (
            str(env.get("PREGACAO_PIN", "") or "").strip() or config.pin
        )
        # PIN das CONFIGURACOES AVANCADAS. As rotas de rede (Wi-Fi) sao
        # @require_admin, entao o agente precisa dele para aceitar um comando
        # Alterar o destino exige PIN de administrador.
        # Mesma regra de auth.admin_pin(): vazio cai para o PIN normal.
        self.admin_pin = (
            str(env.get("PREGACAO_ADMIN_PIN", "") or "").strip() or config.pin
        )
        # identidade do aparelho: PREGACAO_DEVICE_ID -> config.json -> gerado
        env_device = str(env.get("PREGACAO_DEVICE_ID", "") or "").strip()
        self.device_id = sanitize_device_id(env_device) if env_device else config.device_id
        # credencial do operador no servico remoto (para o painel exibir ao
        # administrador, que digita no APK uma unica vez)
        self.operator_token = str(env.get("PREGACAO_OPERATOR_TOKEN", "") or "").strip()

    @property
    def configured(self) -> bool:
        """Existe um servico remoto apontado?"""
        return bool(self.host)

    @property
    def disabled(self) -> bool:
        """Alguem desligou o agente explicitamente no .env?"""
        return self.enabled_flag.strip().lower() in _DISABLED_VALUES

    @property
    def enabled(self) -> bool:
        return self.configured and not self.disabled

    @property
    def username_or_device(self) -> str:
        """Identidade MQTT: o username padrao e o proprio device_id."""
        return self.username or self.device_id


# ======================================================================
# API local do proprio equipamento
# ======================================================================
class LocalApi:
    """Cliente minimo da API local (127.0.0.1). Reautentica em 401."""

    def __init__(
        self,
        base: str,
        pin: str,
        timeout: float = 20.0,
        admin_pin: str = "",
    ) -> None:
        self.base = base.rstrip("/")
        self.pin = pin
        self.admin_pin = admin_pin
        self.timeout = timeout
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar)
        )

    # -- nucleo ----------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header(CABECALHO_AGENTE, VERSAO_AGENTE)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with self._opener.open(req, timeout=timeout or self.timeout) as resp:
                raw = resp.read().decode(errors="replace")
                try:
                    return int(resp.status), json.loads(raw or "{}")
                except ValueError:
                    return int(resp.status), {"raw": raw}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                payload = json.loads(raw or "{}")
            except ValueError:
                payload = {"raw": raw}
            return int(exc.code), payload
        except (urllib.error.URLError, OSError) as exc:
            return 0, {"error": f"api local indisponivel: {exc}"}

    def _authed(
        self, method: str, path: str, body: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        status, payload = self._request(method, path, body)
        if status == 401 and self.pin and self.login():
            status, payload = self._request(method, path, body)
        return status, payload

    def _admined(
        self, method: str, path: str, body: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, Any]]:
        """Como ``_authed``, mas garantindo a sessao de administrador.

        As rotas de rede sao ``@require_admin``: sem ``session["admin"]`` o
        servidor devolve 403 ``admin_obrigatorio``. E ``is_admin()`` so vale
        depois do ``/api/login`` com o PIN comum - por isso a ordem importa e
        por isso isso nao pode ficar no ``_authed`` (que seria chamado em
        todas as operacoes).
        """
        status, payload = self._authed(method, path, body)
        if status != 403 or str(payload.get("error") or "") != "admin_obrigatorio":
            return status, payload
        if not self._logged() and not self.login():
            return status, payload
        if not self.admin_login():
            return status, payload
        return self._request(method, path, body)

    # -- operacoes -------------------------------------------------------
    def login(self) -> bool:
        status, _ = self._request("POST", "/api/login", {"pin": self.pin})
        return status == 200

    def admin_login(self) -> bool:
        status, _ = self._request(
            "POST", "/api/admin/login", {"pin": self.admin_pin}
        )
        return status == 200

    def status(self) -> Tuple[int, Dict[str, Any]]:
        return self._authed("GET", "/api/status")

    def start(self) -> Tuple[int, Dict[str, Any]]:
        return self._authed("POST", "/api/start", {})

    def stop(self) -> Tuple[int, Dict[str, Any]]:
        return self._authed("POST", "/api/stop", {})

    def cancel(self) -> Tuple[int, Dict[str, Any]]:
        return self._authed("POST", "/api/cancel", {})

    # -- google drive (o conector do APK) --------------------------------
    def drive_status(self) -> Tuple[int, Dict[str, Any]]:
        return self._authed("GET", "/api/drive/status")

    def drive_connect(self) -> Tuple[int, Dict[str, Any]]:
        """Abre o fluxo e devolve a URL de consentimento do Google."""
        return self._authed("POST", "/api/drive/connect", {})

    def drive_finish(
        self, code: str, state: str = ""
    ) -> Tuple[int, Dict[str, Any]]:
        """Troca o codigo capturado no celular pela credencial."""
        return self._authed(
            "POST", "/api/drive/finish", {"code": code, "state": state}
        )

    def drive_disconnect(self) -> Tuple[int, Dict[str, Any]]:
        return self._authed("POST", "/api/drive/disconnect", {})

    def drive_test(self) -> Tuple[int, Dict[str, Any]]:
        return self._authed("POST", "/api/drive/test", {})

    # -- armazenamento ---------------------------------------------------
    def storage_list(self) -> Tuple[int, Dict[str, Any]]:
        return self._authed("GET", "/api/storage")

    def storage_set(self, path: str) -> Tuple[int, Dict[str, Any]]:
        # trocar o destino e configuracao persistente: mesma protecao de
        # administrador usada pelas rotas de rede
        return self._admined("POST", "/api/storage", {"path": path})

    def pregacoes_list(self) -> Tuple[int, Dict[str, Any]]:
        return self._authed("GET", "/api/pregacoes")

    def pregacao_get(self, pid: int) -> Tuple[int, Dict[str, Any]]:
        return self._authed("GET", f"/api/pregacoes/{pid}")

    def pregacao_create(self, campos: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
        # O PIN permanece somente no PC: os celulares nao precisam informa-lo.
        return self._admined("POST", "/api/pregacoes", campos)

    def pregacao_update(
        self, pid: int, campos: Dict[str, Any],
    ) -> Tuple[int, Dict[str, Any]]:
        return self._admined("PUT", f"/api/pregacoes/{pid}", campos)

    def pregacao_delete(self, pid: int, versao: int) -> Tuple[int, Dict[str, Any]]:
        return self._admined("DELETE", f"/api/pregacoes/{pid}", {"versao": versao})

    def open_stream(self, timeout: float = 90.0) -> Any:
        """Abre o fluxo SSE de eventos (exige sessao valida)."""
        if not self.pin or not self._logged():
            self.login()
        req = urllib.request.Request(self.base + "/api/stream")
        req.add_header(CABECALHO_AGENTE, VERSAO_AGENTE)
        return self._opener.open(req, timeout=timeout)

    def _logged(self) -> bool:
        return any(cookie.name for cookie in self._jar)


# ======================================================================
# agente
# ======================================================================
def _new_client(client_id: str) -> Any:
    """Cria o cliente MQTT compativel com paho 1.x e 2.x.

    O paho 2.x tornou ``callback_api_version`` obrigatorio e ja avisa que a
    v1 sera removida; o 1.x nem tem o parametro (da ``TypeError``). Cada
    geracao cai na proxima tentativa, sem travar o build numa versao especifica.
    """
    try:
        from paho.mqtt.enums import CallbackAPIVersion

        version: Any = CallbackAPIVersion.VERSION2
    except Exception:  # paho 1.x nao tem o modulo enums
        version = None
    if version is None:
        return mqtt.Client(client_id=client_id)  # type: ignore[misc]
    return mqtt.Client(  # type: ignore[misc]
        callback_api_version=version,
        client_id=client_id,
    )


class RemoteAgent:
    """Mantem o equipamento alcancavel de qualquer lugar, via servico remoto."""

    def __init__(
        self,
        settings: Optional[RemoteSettings] = None,
        api: Optional[LocalApi] = None,
        client: Any = None,
    ) -> None:
        self.settings = settings or RemoteSettings()
        self.api = api or LocalApi(
            self.settings.api_base,
            self.settings.pin,
            admin_pin=self.settings.admin_pin,
        )
        self.topics = topics(self.settings.device_id)
        self._client = client
        self._stop = threading.Event()
        self._connected = threading.Event()
        self._last_signature = ""
        self._last_payload: Dict[str, Any] = {}
        self._lock = threading.Lock()
        # guarda de ordem do progresso por job (S3): ultima seq publicada
        # e de qual job - mensagem antiga da fila nunca faz a barra voltar
        self._job_seq = 0
        self._job_visto: Optional[str] = None

    # ------------------------------------------------------------------
    # mqtt
    # ------------------------------------------------------------------
    def _build_client(self) -> Any:
        settings = self.settings
        client = _new_client(f"pregacao-{settings.device_id}")
        client.reconnect_delay_set(min_delay=1, max_delay=60)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        # LWT: se o agente morrer sem desligar, o broker publica "offline"
        client.will_set(self.topics["avail"], OFFLINE, qos=1, retain=True)
        if settings.username_or_device:
            client.username_pw_set(settings.username_or_device, settings.password)
        if settings.tls:
            client.tls_set()  # CA do sistema + verificacao de hostname
        return client

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: Any, *_: Any) -> None:
        code = int(getattr(rc, "value", rc))
        if code != 0:
            log.error("[REMOTE] conexao recusada pelo servico remoto (rc=%s)", code)
            return
        self._connected.set()
        settings = self.settings
        log.info(
            "[REMOTE] conectado a %s:%s (device_id=%s)",
            settings.host,
            settings.port,
            settings.device_id,
        )
        client.subscribe(self.topics["cmd"], qos=1)
        self._publish(self.topics["avail"], ONLINE, retain=True)
        self.publish_state(force=True)
        self.publish_job_snapshot()

    def _on_disconnect(self, client: Any, userdata: Any, *args: Any) -> None:
        # paho v1: (client, userdata, rc)
        # paho v2: (client, userdata, disconnect_flags, reason_code, properties)
        rc = args[1] if len(args) >= 3 else (args[0] if args else 0)
        code = int(getattr(rc, "value", rc) or 0)
        self._connected.clear()
        if code == 0:
            log.info("[REMOTE] desconectado do servico remoto (normal)")
        else:
            log.warning(
                "[REMOTE] conexao com o servico remoto perdida (rc=%s); reconectando",
                code,
            )

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        try:
            parsed = parse_command(message.payload)
            if "error" in parsed:
                log.warning("[REMOTE] comando ignorado: %s", parsed["error"])
                resposta: Dict[str, Any] = {
                    "ok": False,
                    "error": parsed["error"],
                    "ts": time.time(),
                }
                # expirado/invalido ainda informa de qual pedido veio a recusa
                if parsed.get("cmd"):
                    resposta["cmd"] = parsed["cmd"]
                    resposta["req_id"] = parsed.get("req_id") or ""
                self._publish(self.topics["ack"], resposta)
                return
            log.info("[REMOTE] comando recebido: %s", parsed["cmd"])
            ack = self.handle_command(parsed)
            self._publish(self.topics["ack"], ack)
            # qualquer comando pode ter mudado o estado: republica
            self.publish_state(force=True)
        except Exception:  # pragma: no cover - nunca derruba o loop do broker
            log.exception("[REMOTE] falha ao processar comando")

    def _publish(self, topic: str, payload: Any, retain: bool = False, qos: int = 1) -> bool:
        if self._client is None:
            return False
        if not isinstance(payload, str):
            payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        try:
            info = self._client.publish(topic, payload, qos=qos, retain=retain)
            expected = getattr(mqtt, "MQTT_ERR_SUCCESS", 0)
            return int(getattr(info, "rc", expected)) == expected
        except Exception as exc:
            log.warning("[REMOTE] falha ao publicar em %s: %s", topic, exc)
            return False

    def _publica_job(self, payload: Dict[str, Any]) -> bool:
        """Republica o progresso do estudo no topic retido ``jobs`` (S3).

        O payload nasce no app (estudos) e ja vem com ``seq`` monotona:
        a mesma sequencia ou mais antiga (mensagem velha na fila de
        reconexao) e descartada - o celular nunca volta para uma etapa
        que ja passou. Job novo zera a guarda. O ``retain`` faz o
        aparelho que reconectar receber o progresso atual sem reiniciar
        nada. Este e o UNICO topico retido de progresso; comandos
        continuam SEM retain.
        """
        try:
            seq = int(payload.get("seq") or 0)
        except (TypeError, ValueError):
            seq = 0
        job_id = str(payload.get("job_id") or "")
        if job_id and job_id == self._job_visto and seq and seq <= self._job_seq:
            log.debug(
                "[REMOTE] progresso antigo descartado (seq %s <= %s)",
                seq,
                self._job_seq,
            )
            return False
        if job_id:
            self._job_visto = job_id
            self._job_seq = seq
        return self._publish(self.topics["jobs"], payload, retain=True)

    def publish_job_snapshot(self) -> bool:
        """Sincroniza o ultimo job retido ao reconectar o agente.

        O evento SSE final pode ter sido perdido durante uma queda ou uma
        atualizacao. O banco, via API local, e a fonte de verdade do progresso.
        """
        status_code, snapshot = self.api.status()
        if status_code != 200 or not isinstance(snapshot, dict):
            return False
        job = ((snapshot.get("estudos") or {}).get("job") or {})
        if not job.get("job_id"):
            self._job_visto = None
            self._job_seq = 0
            return self._publish(self.topics["jobs"], "", retain=True)
        payload = {
            key: job.get(key)
            for key in ("job_id", "recording_id", "estado", "etapa",
                        "percentual", "descricao", "motivo")
        }
        # Eventos SSE que ficaram na fila antes deste snapshot nao podem
        # substituir no broker o estado final que acaba de vir do banco.
        agora = time.time()
        seq = int(agora * 1000)
        if job["job_id"] == self._job_visto:
            seq = max(seq, self._job_seq + 1)
        payload.update(seq=seq, ts=agora)
        return self._publica_job(payload)

    # ------------------------------------------------------------------
    # estado
    # ------------------------------------------------------------------
    def publish_state(self, force: bool = False) -> bool:
        """Le o estado local e publica somente se algo mudou."""
        with self._lock:
            status_code, snapshot = self.api.status()
            if status_code != 200 or not isinstance(snapshot, dict):
                # API fora do ar (servico reiniciando): mantem a ultima
                # imagem e marca api_ok=False para o APK mostrar o problema.
                payload = dict(self._last_payload or {})
                payload.update(
                    {
                        "device_id": self.settings.device_id,
                        "api_ok": False,
                        "state": payload.get("state") or "ERROR",
                        "ts": time.time(),
                    }
                )
            else:
                payload = project_status(snapshot)
                payload["api_ok"] = True

            sig = signature(payload)
            if not force and sig == self._last_signature:
                return False
            self._last_signature = sig
            self._last_payload = payload
            return self._publish(self.topics["state"], payload, retain=True)

    # ------------------------------------------------------------------
    # comandos de gravacao, Drive e armazenamento -> API local
    # ------------------------------------------------------------------
    def handle_command(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Executa o comando na API local e monta o ACK.

        START e idempotente: se ja existe gravacao ativa, responde ``ok`` com
        ``idempotent`` e NAO inicia uma segunda. STOP sem gravacao ativa faz o
        mesmo (nada e corrompido). A protecao de verdade continua sendo o
        servidor (HTTP 409) - aqui e so o convenio de resposta.

        Alteracoes de armazenamento usam a protecao administrativa da API.
        O controle pelo celular nao altera a rede do PC.
        """
        cmd = parsed.get("cmd", "")
        ack: Dict[str, Any] = {
            "cmd": cmd,
            "req_id": parsed.get("req_id") or "",
            "ok": False,
            "ts": time.time(),
        }
        try:
            status_code, snapshot = self.api.status()
            if status_code != 200 or not isinstance(snapshot, dict):
                ack["error"] = str(
                    (snapshot or {}).get("error") or "sem resposta da API local"
                )
                ack["code"] = "sem_resposta"
                return ack

            state = str(snapshot.get("state") or "")
            ack["state"] = state

            if cmd == "STATUS":
                ack["ok"] = True
                ack["status"] = project_status(snapshot)
                return ack

            if cmd == "START":
                if state == State.RECORDING:
                    ack["ok"] = True
                    ack["idempotent"] = True
                    ack["detail"] = "ja existe gravacao em andamento"
                    return ack
                code, payload = self.api.start()
            elif cmd == "STOP":
                if state == State.FINALIZING:
                    # o arquivo ja esta sendo fechado: nao ha nada a parar
                    ack["ok"] = True
                    ack["idempotent"] = True
                    ack["detail"] = "gravacao ja em finalizacao"
                    return ack
                if state != State.RECORDING:
                    ack["ok"] = True
                    ack["idempotent"] = True
                    ack["detail"] = "nenhuma gravacao em andamento"
                    return ack
                code, payload = self.api.stop()
            elif cmd == "CANCEL":
                if state != State.RECORDING:
                    ack["error"] = "nenhuma gravacao ativa para descartar"
                    ack["code"] = "estado_invalido"
                    return ack
                code, payload = self.api.cancel()
            # -- espelho do painel: google drive --------------------------
            elif cmd == "DRIVE_STATUS":
                code, payload = self.api.drive_status()
            elif cmd == "DRIVE_CONNECT":
                # devolve a URL de consentimento; o APK abre no navegador e
                # captura o retorno em localhost do PROPRIO celular
                code, payload = self.api.drive_connect()
            elif cmd == "DRIVE_FINISH":
                codigo = str(parsed.get("code") or "").strip()
                if not codigo:
                    ack["error"] = "codigo de autorizacao ausente"
                    ack["code"] = "codigo_obrigatorio"
                    return ack
                code, payload = self.api.drive_finish(
                    codigo, str(parsed.get("state") or "")
                )
            elif cmd == "DRIVE_DISCONNECT":
                code, payload = self.api.drive_disconnect()
            elif cmd == "DRIVE_TEST":
                code, payload = self.api.drive_test()
            # -- espelho do painel: onde gravar ---------------------------
            elif cmd == "STORAGE_LIST":
                code, payload = self.api.storage_list()
            elif cmd == "STORAGE_SET":
                caminho = str(parsed.get("path") or "").strip()
                if not caminho:
                    ack["error"] = "destino nao informado"
                    ack["code"] = "path_obrigatorio"
                    return ack
                code, payload = self.api.storage_set(caminho)
            elif cmd == "PREGACAO_LISTAR":
                try:
                    offset = int(parsed.get("offset") or 0)
                except (TypeError, ValueError):
                    offset = -1
                if offset < 0 or offset > 10000:
                    ack.update(error="pagina invalida", code="pagina_invalida")
                    return ack
                code, payload = self.api.pregacoes_list()
            elif cmd in (
                "PREGACAO_OBTER", "PREGACAO_ATUALIZAR", "PREGACAO_DELETAR",
            ):
                try:
                    pid = int(parsed.get("id") or 0)
                except (TypeError, ValueError):
                    pid = 0
                if pid <= 0:
                    ack.update(error="pregacao invalida", code="id_invalido")
                    return ack
                if cmd == "PREGACAO_OBTER":
                    code, payload = self.api.pregacao_get(pid)
                else:
                    try:
                        versao = int(parsed.get("versao") or 0)
                    except (TypeError, ValueError):
                        versao = 0
                    if versao <= 0:
                        ack.update(error="versao invalida", code="versao_invalida")
                        return ack
                    if cmd == "PREGACAO_ATUALIZAR":
                        campos = {k: str(parsed.get(k) or "") for k in PREGACAO_CAMPOS}
                        code, payload = self.api.pregacao_update(
                            pid, {**campos, "versao": versao},
                        )
                    else:
                        code, payload = self.api.pregacao_delete(pid, versao)
            elif cmd == "PREGACAO_CRIAR":
                campos = {k: str(parsed.get(k) or "") for k in PREGACAO_CAMPOS}
                code, payload = self.api.pregacao_create(campos)
            else:  # comando conhecido mas sem ramo: defesa, nao deve ocorrer
                ack["error"] = f"comando nao suportado: {cmd}"
                ack["code"] = "comando_invalido"
                return ack

            if 200 <= code < 300:
                ack["ok"] = True
                ack["state"] = str(payload.get("state") or ack.get("state") or "")
                if cmd == "DRIVE_CONNECT":
                    ack["url"] = str(payload.get("url") or "")
                    ack["redirect_uri"] = str(payload.get("redirect_uri") or "")
                elif cmd == "DRIVE_FINISH":
                    ack["account"] = str(payload.get("account") or "")
                    ack["connected"] = bool(payload.get("connected"))
                elif cmd == "DRIVE_STATUS":
                    # so o que a interface precisa - e o recorte que a rota
                    # ja faz para quem nao e administrador
                    ack["drive"] = {
                        campo: payload.get(campo)
                        for campo in (
                            "libraries", "credentials", "connected",
                            "account", "folder", "auto_upload",
                        )
                    }
                elif cmd in ("DRIVE_DISCONNECT", "DRIVE_TEST"):
                    ack["folder_id"] = str(payload.get("folder_id") or "")
                elif cmd == "STORAGE_LIST":
                    ack["storage"] = payload
                elif cmd == "STORAGE_SET":
                    ack["current"] = str(payload.get("current") or "")
                    ack["detail"] = "destino de gravacao atualizado"
                elif cmd == "CANCEL":
                    ack["detail"] = "gravacao descartada; nenhum estudo ou upload criado"
                elif cmd == "PREGACAO_LISTAR":
                    hoje = date.today().isoformat()
                    registros = list(payload.get("pregacoes") or [])
                    futuras = sorted(
                        (p for p in registros if str(p.get("data") or "") >= hoje),
                        key=lambda p: (p.get("data") or "", p.get("horario") or ""),
                    )
                    anteriores = sorted(
                        (p for p in registros if str(p.get("data") or "") < hoje),
                        key=lambda p: (p.get("data") or "", p.get("horario") or ""),
                        reverse=True,
                    )
                    ack["pregacoes"] = (futuras + anteriores)[offset:offset + 40]
                    ack["total"] = len(registros)
                elif cmd == "PREGACAO_OBTER":
                    ack["pregacao"] = payload
                elif cmd in (
                    "PREGACAO_CRIAR", "PREGACAO_ATUALIZAR", "PREGACAO_DELETAR",
                ):
                    ack["id"] = int(payload.get("id") or parsed.get("id") or 0)
                    if isinstance(payload.get("pregacao"), dict):
                        ack["pregacao"] = payload["pregacao"]
                    ack["detail"] = "programacao atualizada"
            else:
                ack["error"] = str(
                    payload.get("message")
                    or payload.get("error")
                    or f"HTTP {code}"
                )
                ack["code"] = str(payload.get("error") or "estado_invalido")
                ack["state"] = str(payload.get("state") or state)
        except Exception as exc:  # pragma: no cover - defesa contra API estranha
            log.exception("[REMOTE] falha ao executar %s", cmd)
            ack["error"] = str(exc)
            ack["code"] = "erro_interno"
        return ack

    # ------------------------------------------------------------------
    # threads
    # ------------------------------------------------------------------
    def _sse_loop(self) -> None:
        """Encaminha os eventos do equipamento para o topic ``events``."""
        falhas = 0
        while not self._stop.is_set():
            response = None
            try:
                response = self.api.open_stream()
                if falhas:
                    log.info("[REMOTE] fluxo de eventos reconectado ao equipamento")
                falhas = 0
                log.info("[REMOTE] escutando eventos do equipamento")
                for event in iter_sse(_lines(response)):
                    if self._stop.is_set():
                        break
                    kind = (event.get("event") or "").strip()
                    if not kind:
                        continue
                    if kind == "status":
                        self.publish_state()
                    elif kind == "job_progress":
                        # marco real do estudo (S3): repassa ao topic
                        # retido com guarda de sequencia antiga
                        payload = parse_event(event)
                        if payload:
                            self._publica_job(payload.get("data") or {})
                    elif kind in ("tick", "upload_progress"):
                        # progresso fino nao e republicado: o estado ja diz
                        # "ENVIANDO" e o cronometro nasce do started_at
                        continue
                    else:
                        payload = parse_event(event)
                        if payload:
                            self._publish(self.topics["events"], payload)
            except Exception as exc:
                if not self._stop.is_set():
                    falhas += 1
                    if falhas == 1:
                        # so a primeira quebra vira aviso: durante uma queda
                        # longa o journal enche de linha identica e esconde o
                        # problema real (as repetidas ficam em DEBUG)
                        log.warning("[REMOTE] fluxo de eventos encerrado: %s", exc)
                    else:
                        log.debug(
                            "[REMOTE] aguardando a API local (falha %d): %s",
                            falhas,
                            exc,
                        )
                    self.publish_state()  # api_ok=False quando a API cai
            finally:
                if response is not None:
                    try:
                        response.close()
                    except Exception:  # pragma: no cover
                        pass
            self._stop.wait(3)

    def _poll_loop(self) -> None:
        """Rede de seguranca: refaz o estado a cada intervalo mesmo sem SSE."""
        while not self._stop.wait(self.settings.interval):
            try:
                self.publish_state()
            except Exception:  # pragma: no cover
                log.exception("[REMOTE] falha ao atualizar estado")

    # ------------------------------------------------------------------
    # ciclo de vida
    # ------------------------------------------------------------------
    def run(self) -> int:
        settings = self.settings
        if mqtt is None:
            log.error(
                "[REMOTE] paho-mqtt nao instalado; rode "
                "'.venv/bin/pip install -r requirements.txt'"
            )
            return 1

        self._client = self._build_client()
        log.info(
            "[REMOTE] agente iniciando (broker=%s:%s tls=%s device_id=%s api=%s)",
            settings.host,
            settings.port,
            settings.tls,
            settings.device_id,
            settings.api_base,
        )

        self._client.connect_async(settings.host, settings.port, keepalive=settings.keepalive)
        self._client.loop_start()

        threads = [
            threading.Thread(target=self._sse_loop, name="remote-sse", daemon=True),
            threading.Thread(target=self._poll_loop, name="remote-poll", daemon=True),
        ]
        for thread in threads:
            thread.start()

        try:
            while not self._stop.wait(1.0):
                pass
        except KeyboardInterrupt:  # pragma: no cover
            pass
        finally:
            self.shutdown()
        return 0

    def stop(self) -> None:
        self._stop.set()

    def shutdown(self) -> None:
        log.info("[REMOTE] encerrando agente")
        self._stop.set()
        client = self._client
        if client is None:
            return
        try:
            if self._connected.is_set():
                # aviso limpo antes do LWT assumir
                self._publish(self.topics["avail"], OFFLINE, retain=True)
                time.sleep(0.5)
        except Exception:  # pragma: no cover
            log.debug("[REMOTE] falha ao publicar offline final", exc_info=True)
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:  # pragma: no cover
            log.debug("[REMOTE] falha ao desligar o cliente MQTT", exc_info=True)
        self._connected.clear()


def _lines(response: Any) -> Iterator[str]:
    """Itera linhas de um objeto de resposta HTTP (bytes -> str)."""
    for raw in response:
        if isinstance(raw, (bytes, bytearray)):
            yield bytes(raw).decode("utf-8", "replace")
        else:
            yield str(raw)


# ======================================================================
# trava de instancia unica
# ======================================================================
def _pid_vivo(pid: int) -> bool:
    """True se o PID existe. (os.kill(pid, 0) no Windows TERMINA o
    processo - por isso o caminho nativo via OpenProcess.)"""
    if pid <= 0:
        return False
    if os.name == "nt":  # pragma: no cover - so Windows
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # existe, mas nao é nosso
    except OverflowError:  # pragma: no cover
        return False
    return True


class TravaInstancia:
    """Impede dois agentes simultaneos no mesmo equipamento.

    Sem esta trava, abrir o bat duas vezes faz uma janela derrubar a outra
    (mesmo client ID no broker) e o ``avail`` pisca offline/online - o
    celular fica sem status estavel (o OFFLINE relatado pelo usuario).
    """

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self._minha = False

    def adquirir(self) -> bool:
        pid_antigo = 0
        try:
            pid_antigo = int(self.caminho.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            pid_antigo = 0
        if pid_antigo and _pid_vivo(pid_antigo):
            return False
        try:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            self.caminho.write_text(str(os.getpid()), encoding="utf-8")
        except OSError:
            # sem permissao de escrita: nao ha como garantir exclusao, mas
            # travar a subida do agente por isso seria pior que o problema
            log.warning("[REMOTE] sem permissao para gravar %s", self.caminho)
            self._minha = True
            return True
        self._minha = True
        return True

    def liberar(self) -> None:
        if not self._minha:
            return
        try:
            if self.caminho.read_text(encoding="utf-8").strip() == str(os.getpid()):
                self.caminho.unlink()
        except OSError:
            pass
        self._minha = False


# ======================================================================
# entrada
# ======================================================================
def main(argv: Optional[List[str]] = None) -> int:
    load_env()
    setup_logging()
    settings = RemoteSettings()

    if settings.disabled:
        log.info("[REMOTE] agente desativado (PREGACAO_REMOTE_ENABLED=%s)",
                 settings.enabled_flag)
        return 0
    if not settings.configured:
        log.info(
            "[REMOTE] PREGACAO_REMOTE_HOST ausente; controle remoto nao configurado "
            "(o equipamento segue funcionando normalmente)"
        )
        return 0

    trava = TravaInstancia(paths.home() / "logs" / "agente.pid")
    if not trava.adquirir():
        log.error(
            "[REMOTE] outro agente ja esta rodando neste equipamento; "
            "feche a outra janela (a segunda instancia derrubaria a primeira "
            "no broker e o celular ficaria OFFLINE)"
        )
        return 1

    agent = RemoteAgent(settings)

    def handler(signum: Any, _frame: Any) -> None:
        log.info("[REMOTE] sinal %s recebido; encerrando", signum)
        agent.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):  # pragma: no cover
            pass

    try:
        return agent.run()
    finally:
        trava.liberar()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
