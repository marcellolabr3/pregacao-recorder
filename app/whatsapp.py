"""Sessao e reenvio do WhatsApp; nenhum estado e chamado de entrega sem recibo."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .config import config
from .db import db
from .logging_setup import get

log = get("whatsapp")
operation_lock = threading.RLock()
_state_lock = threading.Lock()
_state: dict[str, Any] = {"busy": False, "action": "", "result": "", "detail": "", "home": ""}


def parse_numbers(raw: str) -> list[str]:
    """Aceita um numero legado ou lista separada por virgula, espaco ou linha."""
    numbers: list[str] = []
    for part in re.split(r"[,;\s]+", str(raw or "").strip()):
        if not part:
            continue
        number = part.removeprefix("+")
        if not number.isdigit() or not 10 <= len(number) <= 15:
            raise ValueError("Use numeros com DDI e DDD (10 a 15 digitos), separados por virgula ou linha")
        if number not in numbers:
            numbers.append(number)
    if len(numbers) > 20:
        raise ValueError("Limite de 20 numeros de destino")
    return numbers


def recipients() -> list[str]:
    return parse_numbers(str(config.get("estudos.whatsapp", "") or ""))


def pipeline_dir() -> Path:
    return Path(str(config.get("estudos.pasta", "") or "")).resolve()


def data_dir() -> Path:
    return Path(os.environ.get("PREGACAO_PIPELINE_HOME") or pipeline_dir()).resolve()


def _node() -> str:
    node = os.environ.get("PREGACAO_NODE") or shutil.which("node")
    if not node or (os.path.isabs(node) and not Path(node).is_file()):
        raise ValueError("Node.js nao encontrado nesta instalacao")
    return node


def _sender() -> Path:
    script = pipeline_dir() / "whatsapp" / "send.js"
    if not script.is_file():
        raise ValueError("Pipeline do WhatsApp nao encontrado nesta instalacao")
    return script


def _command(*args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PREGACAO_PIPELINE_HOME"] = str(data_dir())
    return subprocess.run(
        [_node(), str(_sender()), *map(str, args)],
        cwd=str(pipeline_dir()), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def status() -> dict[str, Any]:
    folder = data_dir()
    with _state_lock:
        state = dict(_state)
    qr_files = sorted((folder / "whatsapp").glob("qr_*.png"), key=lambda p: p.stat().st_mtime)
    qr = bool(qr_files and time.time() - qr_files[-1].stat().st_mtime < 180)
    credentials = (folder / "whatsapp" / "auth" / "creds.json").is_file()
    return {
        **{key: value for key, value in state.items() if key != "home"},
        "configured": (pipeline_dir() / "whatsapp" / "send.js").is_file(),
        "session_saved": credentials,
        "qr_ready": qr and state["busy"] and state["action"] == "login",
        "recipients": recipients(),
        "connection": "verificada" if credentials and state["result"] == "conectado" and state["home"] == str(folder) else (
            "sessao_salva_nao_verificada" if credentials else "login_necessario"
        ),
    }


def qr_path() -> Path | None:
    state = status()
    if not state["qr_ready"]:
        return None
    files = sorted((data_dir() / "whatsapp").glob("qr_*.png"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _set_state(**fields: Any) -> None:
    with _state_lock:
        _state.update(fields)


def start_connection(action: str) -> bool:
    if action not in ("login", "check"):
        raise ValueError("acao invalida")
    _node()
    _sender()
    with _state_lock:
        if _state["busy"]:
            return False
        _state.update(busy=True, action=action, result="", detail="", home=str(data_dir()))
    if action == "login":
        for old in (data_dir() / "whatsapp").glob("qr_*.png"):
            try:
                old.unlink()
            except OSError:
                pass

    def worker() -> None:
        try:
            with operation_lock:
                result = _command("--login", "--no-open", timeout=180) if action == "login" else _command("--status", timeout=45)
            ok = result.returncode == 0
            detail = (result.stderr or result.stdout or "").strip().splitlines()[-1:]
            _set_state(result="conectado" if ok else "erro", detail=(detail[0] if detail else "Falha de conexao")[:240])
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            _set_state(result="erro", detail=str(exc)[:240])
        finally:
            _set_state(busy=False, action="")

    threading.Thread(target=worker, name=f"whatsapp-{action}", daemon=True).start()
    return True


def _pdf_for_job(job_id: str) -> Path:
    job = db.get_job(job_id)
    if not job or job["estado"] not in ("CONCLUIDO", "ERRO"):
        raise ValueError("Estudo ainda nao terminou ou nao existe")
    artifact = db.study_artifact(job_id) or {}
    value = artifact.get("pdf_path")
    if not value:
        value = _logged_value(job, ("ARQUIVO_PDF:", "PDF:"))
    if not value:
        raise ValueError("PDF deste estudo nao foi localizado")
    pdf = Path(value).resolve()
    output = (data_dir() / "output").resolve()
    if not pdf.is_relative_to(output) or pdf.suffix.lower() != ".pdf" or not pdf.is_file():
        raise ValueError("PDF deste estudo indisponivel nesta instalacao")
    return pdf


def _logged_value(job: dict[str, Any], prefixes: tuple[str, ...]) -> str:
    if not job.get("resultado"):
        return ""
    try:
        for line in Path(job["resultado"]).read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith(prefixes):
                return stripped.partition(":")[2].strip()
    except OSError:
        pass
    return ""


def mind_map_path(job_id: str) -> Path:
    job = db.get_job(job_id)
    artifact = db.study_artifact(job_id) or {}
    value = artifact.get("mind_map_path") or (_logged_value(job, ("ARQUIVO_MAPA:",)) if job else "")
    if not job or not value:
        raise ValueError("Mapa mental deste estudo indisponivel")
    path = Path(value).resolve()
    output = (data_dir() / "output").resolve()
    if not path.is_relative_to(output) or path.suffix.lower() != ".json" or not path.is_file():
        raise ValueError("Mapa mental deste estudo indisponivel nesta instalacao")
    return path


def list_studies(limit: int = 20) -> list[dict[str, Any]]:
    result = []
    for job in db.list_jobs(limit):
        try:
            _pdf_for_job(job["job_id"])
            available = True
        except ValueError:
            available = False
        try:
            mind_map_path(job["job_id"])
            map_available = True
        except ValueError:
            map_available = False
        artifact = db.study_artifact(job["job_id"]) or {}
        result.append({
            "job_id": job["job_id"],
            "audio": Path(job["audio_path"]).stem,
            "estado": job["estado"], "etapa": job["etapa"],
            "created_at": job["created_at"], "pdf_available": available,
            "mind_map_available": map_available,
            "mind_map_error": artifact.get("mind_map_error") or _logged_value(job, ("MAPA_ERRO:",)),
            "sends": db.list_whatsapp_sends(job["job_id"]),
        })
    return result


def resend(job_id: str, numbers: str) -> list[int]:
    pdf = _pdf_for_job(job_id)
    chosen = parse_numbers(numbers)
    if not chosen:
        raise ValueError("Informe pelo menos um numero de destino")
    _node()
    _sender()
    send_ids = [db.record_whatsapp_send(job_id, number, "PENDENTE") for number in chosen]

    def worker() -> None:
        for number, send_id in zip(chosen, send_ids):
            try:
                with operation_lock:
                    result = _command(number, str(pdf), "Estudo devocional (reenvio)")
                if result.returncode == 0 and "ACEITO:" in result.stdout:
                    message_id = result.stdout.partition("ACEITO:")[2].splitlines()[0].strip()
                    db.update_whatsapp_send(send_id, "ACEITO_PELO_SERVIDOR", message_id=message_id)
                else:
                    detail = (result.stderr or result.stdout or "Falha no envio").strip().splitlines()[-1]
                    db.update_whatsapp_send(send_id, "FALHOU", error=detail)
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                db.update_whatsapp_send(send_id, "FALHOU", error=str(exc))

    threading.Thread(target=worker, name="whatsapp-reenvio", daemon=True).start()
    return send_ids
