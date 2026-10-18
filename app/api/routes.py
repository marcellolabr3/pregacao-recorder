"""API HTTP + SSE. Toda a logica de negocio fica nos modulos, aqui e apenas I/O."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

from flask import Response, jsonify, request, stream_with_context

from .. import estudos, notify, paths
from ..audio import device as audio_device
from ..config import config
from ..db import db
from ..events import bus
from ..importacao import (
    PregacaoImportada,
    gerar_modelo_csv,
    gravar_pregacoes,
    importar_csv,
    importar_xlsx,
)
from ..logging_setup import get
from ..recording.manager import ManagerError, RecordingManager
from ..states import InvalidTransition, State, state_machine
from ..storage import destinos, layout
from ..upload import drive
from ..upload.queue import UploadWorker, internet_available
from . import auth
from .network_routes import register_network_routes

log = get("api")

# ultima vez que o agente MQTT bateu na API local. Toda chamada dele
# traz o cabecalho X-Pregacao-Agent (app/remote/agent.py, constante
# CABECALHO_AGENTE - o literal mora aqui para nao puxar o paho-mqtt no
# boot do painel); o /api/integracoes so declara o EMQX conectado com
# batida recente de verdade - nada simulado.
_agente_visto_em = 0.0


def _registra_agente() -> None:
    global _agente_visto_em
    if request.headers.get("X-Pregacao-Agent"):
        _agente_visto_em = time.time()

AUDIO_FORMATS = ["S16_LE", "S32_LE", "U8", "S24_3LE"]
ENCODERS = ["mp3", "wav"]
BITRATES = [64, 96, 128, 192, 256, 320]
RATES = [16000, 22050, 32000, 44100, 48000]


def _err(message: str, status: int = 400, code: str = "erro"):
    return jsonify({"error": code, "message": message}), status


def _oauth_page(status: str, message: str) -> str:
    """Pagina de retorno do OAuth.

    Exibe o resultado e devolve o usuario a interface na MESMA ABA
    (o login do Google nao abre popup; a navegacao e feita na aba atual).
    """
    target = f"/config?drive={status}&msg={quote(message, safe='')}"
    heading = "Conta conectada" if status == "ok" else "Falha na conexao"
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Google Drive</title>"
        f"<meta http-equiv='refresh' content='3;url={target}'>"
        f"<script>location.replace(\"{target}\");</script>"
        "</head><body style='font-family:sans-serif;padding:40px;text-align:center'>"
        f"<h2>{heading}</h2><p>{escape(message)}</p>"
        f"<p><a href='{target}'>voltar para a interface</a></p>"
        "</body></html>"
    )


COERCE = {
    "audio.sample_rate": int,
    "audio.channels": int,
    "audio.segment_seconds": int,
    "audio.bitrate": int,
    "storage.min_free_mb": int,
    "storage.retention_days": int,
    "drive.retention_days": int,
    "audio.device": str,
    "audio.format": str,
    "audio.encoder": str,
    "device_name": str,
    "device_id": str,
    "storage.recordings_dir": str,
    "drive.folder_name": str,
    "drive.folder_id": str,
    "drive.client_id": str,
    "drive.client_secret": str,
    "drive.auto_upload": bool,
    "drive.keep_local": bool,
    "drive.enabled": bool,
    "storage.keep_local": bool,
    "network.check_host": str,
    "network.check_port": int,
    "network.retry_seconds": int,
    "setup.completed": bool,
    "estudos.ativo": bool,
    "estudos.whatsapp": str,
    "estudos.python": str,
    "estudos.pasta": str,
}

# chaves que so o ADMINISTRADOR pode alterar (CONFIGURACOES AVANCADAS)
ADMIN_PREFIXES = ("audio.", "storage.", "network.", "web.")
ADMIN_KEYS = {
    "device_id",
    "drive.client_id",
    "drive.client_secret",
    "drive.folder_name",
    "drive.folder_id",
    "drive.enabled",
    "drive.auto_upload",
    "drive.keep_local",
    "drive.retention_days",
    "estudos.python",
    "estudos.pasta",
}


def needs_admin(key: str) -> bool:
    return key.startswith(ADMIN_PREFIXES) or key in ADMIN_KEYS

VALIDATION = {
    "audio.sample_rate": lambda v: v in RATES,
    "audio.channels": lambda v: v in (1, 2),
    "audio.format": lambda v: v in AUDIO_FORMATS,
    "audio.encoder": lambda v: v in ENCODERS,
    "audio.bitrate": lambda v: v in BITRATES,
    "audio.segment_seconds": lambda v: 10 <= v <= 900,
    "storage.min_free_mb": lambda v: 0 <= v <= 100000,
    "storage.retention_days": lambda v: 0 <= v <= 3650,
    "network.check_port": lambda v: 1 <= v <= 65535,
    "network.retry_seconds": lambda v: 5 <= v <= 3600,
    # Client ID do Google sempre termina em .apps.googleusercontent.com
    "drive.client_id": lambda v: (not v) or v.endswith(".apps.googleusercontent.com"),
    "drive.client_secret": lambda v: (not v) or len(v) >= 8,
    # WhatsApp com DDI: so digitos, opcional "+", de 10 a 15 caracteres
    "estudos.whatsapp": lambda v: (not v)
    or (v.replace("+", "").isdigit() and 10 <= len(v.replace("+", "")) <= 15),
}


# no Windows o systemctl nao existe, mas a flag evita qualquer janela
_FLAGS_SUBPROCESS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _service_state(unit: str) -> str:
    """Estado de uma unit do systemd: active / inactive / failed / ..."""
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=_FLAGS_SUBPROCESS,
        )
        return (proc.stdout or "").strip() or "desconhecido"
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return "desconhecido"


def remote_status() -> Dict[str, Any]:
    """Estado do agente de controle remoto (o caminho do APK).

    Somente administrador: o ``operator_token`` e a credencial que o
    administrador digita uma unica vez no APK, entao este bloco so pode sair
    pela rota que ja exige PIN de administrador.
    """
    from ..remote.agent import RemoteSettings  # import local: nao puxa o
    settings = RemoteSettings()                # paho-mqtt no boot do painel

    return {
        "configured": settings.configured,
        "enabled": settings.enabled,
        "host": settings.host,
        "port": settings.port,
        "tls": settings.tls,
        "device_id": settings.device_id,
        "operator_token": settings.operator_token,
        "service": _service_state("pregacao-remote.service"),
    }


def system_status(manager: RecordingManager, uploader: UploadWorker) -> Dict[str, Any]:
    base = manager.status()
    devices = audio_device.list_devices()
    pending = len(base.get("recovery") or [])
    drive_status = drive.status()
    # o SSD pode ter sido desmontado e o diretorio configurado continuar
    # existindo dentro do cartao SD - sem este aviso a troca passaria
    # despercebida (foi exatamente o relatado pelo usuario).
    armazenamento = destinos.atual(
        config.recordings_root, paths.recordings_dir()
    )
    aviso_armazenamento = destinos.aviso(
        config.recordings_root, paths.recordings_dir()
    )
    # saude da sessao do NotebookLM (leitura em memoria, sem subprocesso)
    est = estudos.status()

    if state_machine.state == State.RECOVERY_REQUIRED or pending or aviso_armazenamento:
        banner = "ATENCAO"
    elif state_machine.state == State.RECORDING:
        banner = "GRAVANDO"
    elif state_machine.state in (State.UPLOADING, State.FINALIZING):
        banner = "ENVIANDO"
    elif state_machine.state == State.ERROR:
        banner = "ATENCAO"
    else:
        banner = "PRONTO"

    base.update(
        {
            "banner": banner,
            "device_name": config.get("device_name", "Pulpito"),
            "device_id": config.device_id,
            "platform": "windows" if os.name == "nt" else "linux",
            "now": time.time(),
            "audio_devices": devices,
            "audio_device_selected": base.get("device"),
            # tile principal do painel: a interface ativa mesmo antes da
            # primeira gravacao (manager.device so existe apos um START)
            "device": base.get("device")
            or audio_device.detect_cached(str(config.get("audio.device", "auto"))),
            "network": {
                "online": internet_available(config),
                "host": config.get("network.check_host"),
            },
            "drive": drive_status,
            "uploads": base.get("uploads") or uploader.snapshot(),
            "recording_dir": str(config.recordings_root),
            "storage_detail": layout.summarize(config.recordings_root),
            "storage_atual": armazenamento,
            "storage_aviso": aviso_armazenamento,
            "estudos": est,
        }
    )
    if est.get("aguardando"):
        # o motivo da pausa vai pelo "detail" do estado - o agente ja
        # republica esse campo para o APK (item: operador precisa saber
        # POR QUE o estudo parou, sem precisar abrir o painel)
        aviso = "AGUARDANDO ESTUDO: " + str(est.get("motivo") or "sessao")
        atual = str(base.get("detail") or "").strip()
        base["detail"] = f"{atual} | {aviso}" if atual else aviso
    return base


def register_routes(app, manager: RecordingManager, uploader: UploadWorker) -> None:
    # rede (Ethernet/Wi-Fi/Access Point/Tailscale) vive em modulo proprio
    register_network_routes(app)

    # batida do agente MQTT em QUALQUER chamada (poll de /api/status,
    # stream SSE, comandos): alimenta o card de saude das integracoes
    @app.before_request
    def _heartbeat_do_agente():
        _registra_agente()

    # ------------------------------------------------------------------
    # autenticacao
    # ------------------------------------------------------------------
    @app.get("/api/me")
    def me():
        payload = auth.session_info()
        payload["device_name"] = config.get("device_name", "Pulpito")
        payload["state"] = state_machine.state
        payload["setup_needed"] = not bool(config.get("setup.completed"))
        return jsonify(payload)

    @app.post("/api/login")
    def login():
        body = request.get_json(silent=True) or {}
        if auth.login(str(body.get("pin", ""))):
            notify.notify("login", "Acesso liberado", level="info")
            return jsonify({"ok": True})
        time.sleep(0.4)  # dificulta forca bruta
        return _err("PIN incorreto", 401, "pin_invalido")

    @app.post("/api/logout")
    def logout():
        auth.logout()
        return jsonify({"ok": True})

    @app.post("/api/admin/login")
    def admin_login():
        body = request.get_json(silent=True) or {}
        if auth.admin_login(str(body.get("pin", ""))):
            notify.notify("admin", "Configuracoes avancadas liberadas", level="info")
            return jsonify({"ok": True, "admin": True})
        time.sleep(0.4)  # dificulta forca bruta
        return _err("PIN de administrador incorreto", 401, "pin_invalido")

    @app.get("/api/admin/status")
    @auth.require_auth
    def admin_status():
        return jsonify(
            {
                "admin": auth.is_admin(),
                "required": auth.admin_configured(),
            }
        )

    # ------------------------------------------------------------------
    # assistente de primeiro acesso
    # ------------------------------------------------------------------
    @app.get("/api/setup")
    @auth.require_auth
    def setup_info():
        return jsonify(
            {
                "needed": not bool(config.get("setup.completed")),
                "audio_device": str(config.get("audio.device", "auto")),
                "recordings_dir": str(config.recordings_root),
                "drive_connected": drive.is_connected(),
                "admin": auth.is_admin(),
            }
        )

    @app.post("/api/setup/complete")
    @auth.require_auth
    def setup_complete():
        config.set("setup.completed", True)
        config.save()
        notify.notify(
            "configuracao",
            "Configuracao inicial concluida - sistema pronto para uso",
            level="success",
        )
        return jsonify({"ok": True, "needed": False})

    # ------------------------------------------------------------------
    # logs (somente administrador)
    # ------------------------------------------------------------------
    @app.get("/api/logs")
    @auth.require_admin
    def logs_tail():
        n = request.args.get("lines", "150")
        try:
            lines = max(10, min(500, int(n)))
        except ValueError:
            lines = 150
        arquivo = paths.logs_dir() / "pregacao.log"
        texto = ""
        if arquivo.exists():
            try:
                with open(arquivo, "r", encoding="utf-8", errors="replace") as fh:
                    texto = "".join(fh.readlines()[-lines:])
            except OSError as exc:
                return _err(f"nao foi possivel ler o log: {exc}", 500)
        return jsonify({"file": str(arquivo), "lines": lines, "content": texto})

    # ------------------------------------------------------------------
    # estado
    # ------------------------------------------------------------------
    @app.get("/api/status")
    def status_endpoint():
        return jsonify(system_status(manager, uploader))

    @app.post("/api/start")
    @auth.require_auth
    def start():
        try:
            result = manager.start()
        except (ManagerError, InvalidTransition) as exc:
            return _err(str(exc), 409, "estado_invalido")
        return jsonify({"ok": True, **result, "state": state_machine.state})

    @app.post("/api/stop")
    @auth.require_auth
    def stop():
        try:
            result = manager.stop()
        except (ManagerError, InvalidTransition) as exc:
            return _err(str(exc), 409, "estado_invalido")
        return jsonify({"ok": True, **result, "state": state_machine.state})

    # ------------------------------------------------------------------
    # recuperacao
    # ------------------------------------------------------------------
    @app.get("/api/recovery")
    @auth.require_auth
    def recovery_list():
        return jsonify({"items": manager.pending_recovery()})

    @app.post("/api/recovery/<session_id>/recover")
    @auth.require_auth
    def recovery_recover(session_id: str):
        try:
            return jsonify({"ok": True, **manager.recover(session_id)})
        except (ManagerError, InvalidTransition) as exc:
            return _err(str(exc), 409, "estado_invalido")

    @app.post("/api/recovery/<session_id>/discard")
    @auth.require_auth
    def recovery_discard(session_id: str):
        try:
            return jsonify({"ok": True, **manager.discard(session_id)})
        except (ManagerError, InvalidTransition) as exc:
            return _err(str(exc), 409, "estado_invalido")

    # ------------------------------------------------------------------
    # gravacoes
    # ------------------------------------------------------------------
    @app.get("/api/recordings")
    @auth.require_auth
    def recordings():
        return jsonify(
            {
                "items": layout.list_recordings(config.recordings_root, limit=50),
                "sessions": db.list_sessions(limit=20),
                "summary": layout.summarize(config.recordings_root),
            }
        )

    @app.get("/api/events/history")
    @auth.require_auth
    def event_history():
        return jsonify({"items": db.list_events(limit=50), "bus": bus.history()})

    # ------------------------------------------------------------------
    # configuracao
    # ------------------------------------------------------------------
    @app.get("/api/config")
    @auth.require_auth
    def get_config():
        st = drive.status()
        if not auth.is_admin():
            # usuario comum: apenas o que a tela CONFIG exibe.
            # Credenciais, caminhos e formatos ficam na area avancada.
            return jsonify(
                {
                    "config": {"device_name": config.get("device_name", "")},
                    "drive": {
                        "connected": st.get("connected"),
                        "credentials": st.get("credentials"),
                        "account": st.get("account"),
                        "folder": st.get("folder"),
                    },
                    "estudos": {
                        "ativo": bool(config.get("estudos.ativo", True)),
                        "whatsapp": str(config.get("estudos.whatsapp", "") or ""),
                    },
                    "admin": False,
                }
            )
        cfg = config.as_dict()
        # identificador efetivo (pode estar vazio no config e ser gerado)
        cfg["device_id"] = config.device_id
        # o secret nunca sai do servidor; a interface so sabe se esta definido
        drive_cfg = cfg.setdefault("drive", {})
        secret = str(drive_cfg.get("client_secret") or "").strip()
        drive_cfg["client_secret_set"] = bool(secret)
        drive_cfg["client_secret"] = ""
        return jsonify(
            {
                "config": cfg,
                "admin": True,
                "remote": remote_status(),
                "audio_devices": audio_device.list_devices(),
                "detected": audio_device.detect(str(config.get("audio.device", "auto"))),
                "drive": st,
                "formats": AUDIO_FORMATS,
                "encoders": ENCODERS,
                "bitrates": BITRATES,
                "rates": RATES,
                "home": str(config.recordings_root.parent),
                "has_ffmpeg": bool(__import__("shutil").which("ffmpeg")),
            }
        )

    @app.post("/api/config")
    @auth.require_auth
    def set_config():
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return _err("payload invalido")

        # CONFIGURACOES AVANCADAS exigem PIN de administrador
        protegidas = sorted(k for k in body if needs_admin(k))
        if protegidas and not auth.is_admin():
            return _err(
                "PIN de administrador necessario para alterar: "
                + ", ".join(protegidas),
                403,
                "admin_obrigatorio",
            )

        applied, errors = [], []
        for key, raw in body.items():
            caster = COERCE.get(key)
            if caster is None:
                errors.append(f"chave desconhecida: {key}")
                continue
            try:
                value = caster(raw) if caster is not bool else bool(raw)
            except (TypeError, ValueError):
                errors.append(f"valor invalido para {key}: {raw!r}")
                continue
            validator = VALIDATION.get(key)
            if validator and not validator(value):
                errors.append(f"valor fora do intervalo permitido: {key}={value!r}")
                continue
            if key == "audio.device" and value:
                known = {d["hw"] for d in audio_device.list_devices()}
                known |= {d["card_id"] for d in audio_device.list_devices()}
                if value not in known and value != "auto":
                    errors.append(f"dispositivo de audio inexistente: {value}")
                    continue
            if key == "storage.recordings_dir" and value:
                # valida no modulo de destinos: so "criar a pasta" aceitaria
                # /mnt/ssd/pregacoes mesmo com o SSD desmontado (a pasta
                # existe na raiz do cartao SD) e o usuario acharia que
                # trocou de destino.
                # Valor igual ao atual nao ha o que validar: o form completo
                # reenvia o campo sempre, e recusar faria o administrador
                # perder qualquer outra alteracao so porque o disco sumiu.
                atual_cfg = str(config.get("storage.recordings_dir") or "")
                if str(value) != atual_cfg:
                    ok, motivo = destinos.escolher(
                        str(value), paths.recordings_dir()
                    )
                    if not ok:
                        errors.append(motivo)
                        continue
            config.set(key, value)
            applied.append(key)
            if key == "drive.client_id" and not value:
                # limpar o Client ID remove as credenciais por completo
                config.set("drive.client_secret", "")
                applied.append("drive.client_secret")

        if errors:
            return _err("; ".join(errors), 422, "config_invalida")
        config.save()
        notify.notify(
            "configuracao",
            "Configuracao atualizada: " + (", ".join(applied) or "nenhuma alteracao"),
            level="success",
            payload={"keys": applied},
        )
        return jsonify({"ok": True, "applied": applied})

    # ------------------------------------------------------------------
    # audio
    # ------------------------------------------------------------------
    @app.get("/api/audio/devices")
    @auth.require_auth
    def audio_devices():
        return jsonify({"items": audio_device.list_devices(),
                        "selected": audio_device.detect(str(config.get("audio.device", "auto")))})

    @app.post("/api/audio/test")
    @auth.require_auth
    def audio_test():
        device = audio_device.detect(str(config.get("audio.device", "auto")))
        result = audio_device.capture_level(
            seconds=2.0, device=device.get("hw")
        )
        result["device"] = device
        if result.get("ok"):
            level = "success" if not result.get("silent") else "warning"
            msg = (
                f"Sinal detectado em {device.get('hw')} "
                f"(pico {result.get('peak_db')} dBFS)"
                if not result.get("silent")
                else "Audio capturado, mas SILÊNCIO (verifique o fader da mesa)"
            )
            notify.notify("audio_teste", msg, level=level)
        else:
            notify.notify("audio_teste", f"Falha no teste: {result.get('error')}", level="error")
        return jsonify(result)

    # ------------------------------------------------------------------
    # armazenamento: onde gravar (SSD, cartao SD, ...)
    # ------------------------------------------------------------------
    @app.get("/api/storage")
    @auth.require_auth
    def storage_list():
        """Destinos disponiveis e situacao do escolhido.

        A lista e montada aqui (e nao dentro do status) porque ler
        ``/proc/mounts`` e medir espaço nao pode entrar no fluxo de status,
        que roda a cada segundo.
        """
        return jsonify(
            {
                "current": str(config.recordings_root),
                "sd_default": str(paths.recordings_dir()),
                "situacao": destinos.atual(
                    config.recordings_root, paths.recordings_dir()
                ),
                "aviso": destinos.aviso(
                    config.recordings_root, paths.recordings_dir()
                ),
                "items": destinos.destinos(
                    config.recordings_root, paths.recordings_dir()
                ),
            }
        )

    @app.post("/api/storage")
    @auth.require_admin
    def storage_set():
        body = request.get_json(silent=True) or {}
        caminho = str(body.get("path") or "").strip()
        ok, motivo = destinos.escolher(caminho, paths.recordings_dir())
        if not ok:
            return _err(motivo, 422, "destino_invalido")
        config.set("storage.recordings_dir", caminho)
        config.save()
        notify.notify(
            "armazenamento",
            f"Destino de gravacao: {caminho}",
            level="success",
            payload={"path": caminho},
        )
        return jsonify({"ok": True, "current": caminho})

    # ------------------------------------------------------------------
    # google drive
    # ------------------------------------------------------------------
    @app.get("/api/drive/status")
    @auth.require_auth
    def drive_status():
        st = drive.status()
        if not auth.is_admin():
            # sem admin: nada de client_id/caminho de credencial
            st = {
                k: st.get(k)
                for k in ("libraries", "credentials", "connected",
                          "account", "folder")
            }
        return jsonify({**st, "auto_upload": config.get("drive.auto_upload")})

    @app.post("/api/drive/connect")
    @auth.require_auth
    def drive_connect():
        if not drive.libraries_available():
            return _err("Bibliotecas do Google nao instaladas neste equipamento.", 501)
        if not drive.credentials_present():
            # o usuario final nunca ve termos tecnicos: quem resolve e o admin
            return _err(
                "Google Drive ainda nao foi configurado neste equipamento. "
                "Solicitacao registrada - contate o administrador.",
                412,
                "drive_nao_configurado",
            )
        redirect = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
        if not redirect:
            # Google SO aceita loopback (localhost/127.0.0.1) em aplicativo
            # de computador: montar a partir do Host do navegador quebra o
            # fluxo quando o painel e aberto pelo nome da maquina ou pelo IP
            # da rede - o Google responde Error 400: invalid_request.
            porta = int(config.get("web.port", 8080) or 8080)
            redirect = f"http://127.0.0.1:{porta}/oauth/callback"
        try:
            url = drive.start_authorization(redirect)
        except drive.DriveError as exc:
            return _err(str(exc), 500)
        return jsonify({"ok": True, "url": url, "redirect_uri": redirect})

    @app.get("/oauth/callback")
    @auth.require_auth
    def oauth_callback():
        """Retorno do Google: mostra o resultado e DEVOLVE a mesma aba a
        interface (o login do Google abre na propria aba, sem popup)."""
        error = request.args.get("error", "").strip()
        code = request.args.get("code", "").strip()
        if error:
            return _oauth_page("erro", f"Google recusou a autorizacao: {error}")
        if not code:
            return _oauth_page("erro", "codigo de autorizacao ausente")
        try:
            drive.finish_authorization(code, request.args.get("state", "").strip())
        except Exception as exc:  # noqa: BLE001
            log.warning("falha no callback do Drive: %s", exc)
            return _oauth_page("erro", f"Falha na autorizacao: {exc}")
        notify.notify(
            "drive_conectado", "Conta Google conectada ao Drive", level="success"
        )
        return _oauth_page("ok", "Conta conectada com sucesso")

    @app.post("/api/drive/finish")
    @auth.require_auth
    def drive_finish():
        """Segundo passo do conector loopback do APK.

        O redirect do Google e ``http://localhost:8080/oauth/callback`` - no
        celular, localhost e o PROPRIO celular, entao o Raspberry nao ouve
        aquele retorno. O navegador captura o codigo e o APK o devolve por
        aqui (pelo agente remoto). O ``state`` acompanha e e conferido contra
        o fluxo aberto, para um codigo de outro pedido nao ser aceito.
        """
        body = request.get_json(silent=True) or {}
        codigo = str(body.get("code") or "").strip()
        if not codigo:
            return _err("codigo de autorizacao ausente", 400, "codigo_ausente")
        try:
            resultado = drive.finish_authorization(
                codigo, str(body.get("state") or "").strip()
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("falha ao finalizar OAuth do Drive: %s", exc)
            return _err(f"Falha na autorizacao: {exc}", 502, "drive_oauth_falhou")
        notify.notify(
            "drive_conectado", "Conta Google conectada ao Drive", level="success"
        )
        return jsonify({"ok": True, **resultado})

    @app.post("/api/drive/disconnect")
    @auth.require_auth
    def drive_disconnect():
        drive.disconnect()
        notify.notify("drive_desconectado", "Conta Google desconectada", level="warning")
        return jsonify({"ok": True})

    @app.post("/api/drive/test")
    @auth.require_auth
    def drive_test():
        try:
            folder = drive.ensure_folder(
                str(config.get("drive.folder_name", "Pregacoes")),
                str(config.get("drive.folder_id", "")),
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"Falha ao acessar o Drive: {exc}", 502)
        return jsonify({"ok": True, "folder_id": folder})

    # ------------------------------------------------------------------
    # upload manual
    # ------------------------------------------------------------------
    @app.post("/api/uploads/retry")
    @auth.require_auth
    def retry_uploads():
        now = time.time()
        with db.connection() as conn:
            cur = conn.execute(
                "UPDATE uploads SET next_attempt = ? WHERE status = 'PENDING'", (now,)
            )
            total = cur.rowcount
        uploader.kick()
        return jsonify({"ok": True, "requeued": total})

    # ------------------------------------------------------------------
    # SSE - atualizacao em tempo real sem recarregar a pagina
    # ------------------------------------------------------------------
    @app.get("/api/stream")
    def stream():
        if not auth.is_authenticated():
            return _err("nao_autenticado", 401)
        q = bus.subscribe()

        def generate():
            try:
                snapshot = system_status(manager, uploader)
                yield f"event: status\ndata: {json.dumps(snapshot)}\n\n"
                last_beat = time.time()
                while True:
                    try:
                        event = q.get(timeout=15)
                    except Exception:  # queue.Empty
                        event = None
                    if event is None:
                        if time.time() - last_beat > 15:
                            yield ": keep-alive\n\n"
                            last_beat = time.time()
                        continue
                    last_beat = time.time()
                    yield f"event: {event['kind']}\ndata: {json.dumps(event)}\n\n"
                    if event["kind"] in ("status", "tick"):
                        continue
                    # sempre que algo muda, reenvia o estado completo
                    try:
                        snap = system_status(manager, uploader)
                        yield f"event: status\ndata: {json.dumps(snap)}\n\n"
                    except Exception:  # pragma: no cover
                        log.exception("falha ao montar status para o SSE")
            finally:
                bus.unsubscribe(q)

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                # "Connection" NAO entra aqui: e header hop-by-hop e pertence ao
                # servidor (PEP 3333). Defini-lo faz o waitress levantar
                # AssertionError e devolver 500, derrubando o fluxo ao vivo do
                # painel. O keep-alive ja e o padrao do proprio servidor.
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ------------------------------------------------------------------
    @app.get("/api/ping")
    def ping():
        return jsonify({"ok": True, "ts": time.time()})

    # ------------------------------------------------------------------
    # estudo automatico - saude da sessao do NotebookLM (separada do Drive)
    # ------------------------------------------------------------------
    @app.get("/api/estudos/status")
    @auth.require_auth
    def estudos_status():
        return jsonify(estudos.status())

    @app.get("/api/integracoes")
    @auth.require_auth
    def integracoes():
        """Saude das integracoes (S3): Drive, NotebookLM, WhatsApp e EMQX.

        Cada bloco com estado padrao (conectado / nao_configurado /
        verificando / autenticacao_necessaria / erro), resultado REAL e a
        acao necessaria quando precisar de intervencao. Nada e estimado:
        Drive e pelo proprio conector, NotebookLM pelo cache de saude,
        WhatsApp pelo ultimo job no banco e EMQX pela batida recente do
        agente (cabecalho visto no before_request).
        """
        agora = time.time()
        saida: Dict[str, Any] = {}

        # --- Google Drive ----------------------------------------------
        d = drive.status()
        if d.get("connected"):
            saida["drive"] = {
                "estado": "conectado",
                "detalhe": (
                    f"conta {d.get('account') or '?'} - "
                    f"pasta {d.get('folder') or '?'}"
                ),
                "acao": "",
            }
        elif not d.get("credentials"):
            saida["drive"] = {
                "estado": "nao_configurado",
                "detalhe": "credenciais OAuth ausentes",
                "acao": "conecte a conta Google (botao Conectar no painel)",
            }
        else:
            saida["drive"] = {
                "estado": "erro",
                "detalhe": "credenciais presentes, sessao desconectada",
                "acao": "refaca a conexao do Drive",
            }

        # --- NotebookLM -------------------------------------------------
        nlm = estudos.status()
        mapa_nlm = {
            "ok": ("conectado", "sessao valida", ""),
            "auth": (
                "autenticacao_necessaria",
                "sessao do Google expirada",
                "renove o login (botao Renovar sessao) - nada se perde, "
                "os estudos ficam em espera",
            ),
            "rede": (
                "erro",
                "sem resposta do NotebookLM",
                "verifique a internet do equipamento",
            ),
            "desconhecido": (
                "verificando",
                "ainda nao verificado nesta subida",
                "use o botao Diagnosticar",
            ),
        }
        nlm_estado, nlm_detalhe, nlm_acao = mapa_nlm.get(
            str(nlm.get("estado") or "desconhecido"), mapa_nlm["desconhecido"]
        )
        if nlm.get("aguardando"):
            nlm_detalhe += f" - {nlm['aguardando']} estudo(s) em espera"
        saida["notebooklm"] = {
            "estado": nlm_estado,
            "detalhe": nlm_detalhe,
            "acao": nlm_acao,
            "verificado_em": nlm.get("verificado_em", 0.0),
        }

        # --- WhatsApp ---------------------------------------------------
        numero = str(config.get("estudos.whatsapp", "") or "").strip()
        jobs = db.list_jobs(1)
        ultimo = jobs[0] if jobs else None
        if not numero:
            saida["whatsapp"] = {
                "estado": "nao_configurado",
                "detalhe": "sem numero de destino",
                "acao": "defina o numero em Estudo automatico",
                "ultimo_finished_at": None,
            }
        elif not ultimo or not ultimo.get("finished_at"):
            saida["whatsapp"] = {
                "estado": "verificando",
                "detalhe": "numero configurado, sem envio registrado ainda",
                "acao": "",
                "ultimo_finished_at": None,
            }
        elif str(ultimo.get("etapa")) == "FINAL":
            saida["whatsapp"] = {
                "estado": "conectado",
                "detalhe": "ultimo estudo enviado em "
                + datetime.fromtimestamp(
                    float(ultimo["finished_at"])
                ).strftime("%d/%m %H:%M"),
                "acao": "",
                "ultimo_finished_at": ultimo.get("finished_at"),
            }
        elif str(ultimo.get("etapa")) == "FINAL_SEM_ENVIO":
            saida["whatsapp"] = {
                "estado": "nao_configurado",
                "detalhe": "ultimo estudo concluiu sem enviar (envio pulado)",
                "acao": "confira o numero de destino",
                "ultimo_finished_at": ultimo.get("finished_at"),
            }
        else:
            saida["whatsapp"] = {
                "estado": "erro",
                "detalhe": str(ultimo.get("erro") or "ultimo estudo falhou")[
                    :160
                ],
                "acao": "veja o ultimo estudo no painel e corrija a causa",
                "ultimo_finished_at": ultimo.get("finished_at"),
            }

        # --- EMQX (agente MQTT) ------------------------------------------
        from ..remote.agent import RemoteSettings  # import local: nao puxa
        settings = RemoteSettings()                # paho-mqtt no boot

        visto = _agente_visto_em
        if not settings.configured:
            saida["emqx"] = {
                "estado": "nao_configurado",
                "detalhe": "sem broker configurado (.env do agente)",
                "acao": "siga docs/EMQX.md para apontar o agente",
                "visto_em": visto,
            }
        elif not settings.enabled:
            saida["emqx"] = {
                "estado": "nao_configurado",
                "detalhe": "controle remoto desligado no .env",
                "acao": "remova PREGACAO_REMOTE_ENABLED=0 para ligar",
                "visto_em": visto,
            }
        elif visto and agora - visto < 180:
            saida["emqx"] = {
                "estado": "conectado",
                "detalhe": (
                    f"agente batendo ha {int(agora - visto)}s "
                    f"(broker {settings.host}:{settings.port})"
                ),
                "acao": "",
                "visto_em": visto,
            }
        else:
            saida["emqx"] = {
                "estado": "verificando",
                "detalhe": (
                    f"broker {settings.host}:{settings.port} configurado, "
                    "sem batida recente do agente"
                ),
                "acao": "abra o iniciar-agente.bat e veja se mostra conectado",
                "visto_em": visto,
            }

        saida["verificado_em"] = agora
        return jsonify(saida)

    # =====================================================================
    # S4: programacao de pregacoes (metadados) + importacao CSV/XLSX
    # =====================================================================
    @app.get("/api/pregacoes")
    @auth.require_auth
    def listar_pregacoes():
        data_de = request.args.get("data_de")
        data_ate = request.args.get("data_ate")
        pregacoes = db.list_pregacoes(data_de, data_ate)
        return jsonify({"pregacoes": pregacoes})

    @app.get("/api/pregacoes/<int:pid>")
    @auth.require_auth
    def obter_pregacao(pid: int):
        p = db.get_pregacao(pid)
        if not p:
            return _err("Pregacao nao encontrada", 404, "nao_encontrado")
        return jsonify(p)

    @app.post("/api/pregacoes")
    @auth.require_admin
    def criar_pregacao():
        body = request.get_json(silent=True) or {}
        try:
            pid = db.create_pregacao(
                data=str(body.get("data", "") or "").strip(),
                horario=str(body.get("horario", "") or "").strip(),
                pregador=str(body.get("pregador", "") or "").strip(),
                igreja=str(body.get("igreja", "") or "").strip(),
                texto_base=str(body.get("texto_base", "") or "").strip(),
                tema=str(body.get("tema", "") or "").strip(),
            )
        except sqlite3.IntegrityError:
            return _err(
                "Ja existe pregacao nesta data e horario", 409, "duplicata"
            )
        return jsonify({"id": pid, "ok": True})

    @app.put("/api/pregacoes/<int:pid>")
    @auth.require_admin
    def atualizar_pregacao(pid: int):
        body = request.get_json(silent=True) or {}
        ok = db.update_pregacao(
            pid,
            data=body.get("data"),
            horario=body.get("horario"),
            pregador=body.get("pregador"),
            igreja=body.get("igreja"),
            texto_base=body.get("texto_base"),
            tema=body.get("tema"),
        )
        if not ok:
            return _err("Pregacao nao encontrada ou versao desatualizada", 404, "nao_encontrado")
        return jsonify({"ok": True})

    @app.delete("/api/pregacoes/<int:pid>")
    @auth.require_admin
    def deletar_pregacao(pid: int):
        ok = db.delete_pregacao(pid)
        if not ok:
            return _err("Pregacao nao encontrada", 404, "nao_encontrado")
        return jsonify({"ok": True})

    @app.post("/api/importacao/previa")
    @auth.require_admin
    def importacao_previa():
        """Le CSV ou XLSX (multipart) e devolve previa: validos, erros, duplicatas.
        Nao grava nada no banco."""
        if "arquivo" not in request.files:
            return _err("arquivo nao enviado", 400, "arquivo_ausente")
        f = request.files["arquivo"]
        nome = f.filename or ""
        extensao = Path(nome).suffix.lower()
        conteudo = f.read()
        try:
            if extensao == ".csv":
                texto = conteudo.decode("utf-8", errors="replace")
                resultado = importar_csv(texto, db.get_pregacao_por_data_horario)
            elif extensao in (".xlsx", ".xls"):
                # salva temporario para openpyxl
                import tempfile
                with tempfile.NamedTemporaryFile(
                    suffix=extensao, delete=False
                ) as tmp:
                    tmp.write(conteudo)
                    tmp_path = Path(tmp.name)
                try:
                    resultado = importar_xlsx(tmp_path, db.get_pregacao_por_data_horario)
                finally:
                    tmp_path.unlink(missing_ok=True)
            else:
                return _err("formato nao suportado (use .csv ou .xlsx)", 400, "formato_invalido")
        except Exception as exc:  # noqa: BLE001
            return _err(f"falha ao ler arquivo: {exc}", 400, "leitura_falhou")

        return jsonify({
            "validos": [p.to_dict() for p in resultado.validos],
            "erros": resultado.erros,
            "duplicatas": resultado.duplicatas,
        })

    @app.post("/api/importacao/confirmar")
    @auth.require_admin
    def importacao_confirmar():
        """Recebe a lista de validos (ja validados na previa) e grava no banco."""
        body = request.get_json(silent=True) or {}
        validos = body.get("validos", [])
        if not isinstance(validos, list) or not validos:
            return _err("nenhuma pregacao valida para gravar", 400, "vazio")
        pregacoes = [
            PregacaoImportada(
                data=str(v.get("data", "")).strip(),
                horario=str(v.get("horario", "")).strip(),
                pregador=str(v.get("pregador", "")).strip(),
                igreja=str(v.get("igreja", "")).strip(),
                texto_base=str(v.get("texto_base", "")).strip(),
                tema=str(v.get("tema", "")).strip(),
                linha_origem=0,
            )
            for v in validos
        ]
        try:
            ids = gravar_pregacoes(db, pregacoes)
        except sqlite3.IntegrityError:
            return _err("duplicata detectada na gravacao", 409, "duplicata")
        return jsonify({"gravados": len(ids), "ids": ids, "ok": True})

    @app.get("/api/importacao/modelo")
    @auth.require_auth
    def importacao_modelo():
        """Devolve CSV modelo para download."""
        from flask import Response
        csv_texto = gerar_modelo_csv()
        return Response(
            csv_texto,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=modelo_pregacoes.csv"},
        )

    @app.post("/api/estudos/diagnosticar")
    @auth.require_auth
    def estudos_diagnosticar():
        if not auth.is_admin():
            return _err(
                "apenas administrador pode verificar a sessao", 403,
                "admin_necessario",
            )
        try:
            return jsonify(estudos.diagnosticar())
        except Exception as exc:  # noqa: BLE001
            log.warning("diagnostico do NotebookLM falhou: %s", exc)
            return _err(f"Falha ao verificar a sessao: {exc}", 502)

    @app.post("/api/estudos/reconectar")
    @auth.require_auth
    def estudos_reconectar():
        if not auth.is_admin():
            return _err(
                "apenas administrador pode renovar o login", 403,
                "admin_necessario",
            )
        try:
            return jsonify(estudos.reconectar())
        except ValueError as exc:
            return _err(str(exc), 412)
        except Exception as exc:  # noqa: BLE001
            log.warning("abertura do login do NotebookLM falhou: %s", exc)
            return _err(f"Falha ao abrir o login: {exc}", 502)

    # vigilancia passiva da sessao (inofensiva quando nao configurado)
    estudos.iniciar()
