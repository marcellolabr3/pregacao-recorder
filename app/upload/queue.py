"""Fila persistente de uploads.

Requisitos atendidos:
  * gravacao concluida com internet fora -> arquivo fica no SSD, status PENDING;
  * reinicializacao -> a fila continua de onde parou (esta no SQLite);
  * reenvio -> nunca envia o mesmo arquivo duas vezes (confirma por ``file_id``);
  * Drive fora do ar -> nova tentativa com backoff exponencial.
"""
from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import Config
from ..db import Database
from ..events import bus
from ..logging_setup import get
from ..notify import notify
from ..states import State, state_machine
from . import drive

log = get("upload.queue")

BACKOFF = [15, 30, 60, 120, 300, 600, 900, 1800]


def internet_available(cfg: Config) -> bool:
    host = str(cfg.get("network.check_host", "www.googleapis.com"))
    port = int(cfg.get("network.check_port", 443))
    try:
        with socket.create_connection((host, port), timeout=5):
            return True
    except OSError:
        return False


class UploadWorker:
    def __init__(self, cfg: Config, database: Database) -> None:
        self.cfg = cfg
        self.db = database
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_error: Optional[str] = None
        self.last_result: Optional[Dict[str, Any]] = None
        self.online: Optional[bool] = None

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="upload-worker", daemon=True)
        self._thread.start()
        log.info("worker de upload iniciado")

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=10)

    def kick(self) -> None:
        """Acorda a fila (usado quando uma nova gravacao fica pronta)."""
        self._wake.set()

    # ------------------------------------------------------------------
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:  # pragma: no cover
                log.exception("erro no ciclo de upload")
            self._wake.wait(timeout=int(self.cfg.get("network.retry_seconds", 30)))
            self._wake.clear()

    def _tick(self) -> None:
        pending = self.db.upload_stats().get("PENDING", 0) + self.db.upload_stats().get("RUNNING", 0)
        if not pending:
            self.online = internet_available(self.cfg)
            return

        if not self.cfg.get("drive.auto_upload", True):
            return

        if not drive.is_connected():
            self.last_error = "Google Drive nao conectado"
            if self.online is not False:
                self.online = False
                notify(
                    "upload_pendente",
                    f"{pending} upload(s) pendente(s): Drive nao conectado",
                    level="warning",
                )
            return

        self.online = internet_available(self.cfg)
        if not self.online:
            self.last_error = "sem internet"
            log.info("sem internet; %d upload(s) na fila", pending)
            return

        for item in self.db.claim_pending_uploads(limit=3):
            self._process(item)

    # ------------------------------------------------------------------
    def _process(self, item: Dict[str, Any]) -> None:
        upload_id = item["id"]
        path = Path(item["file_path"])
        attempts = int(item.get("attempts") or 0)
        notify("upload_inicio", f"Enviando {path.name} para o Google Drive", level="info")

        previous_state = state_machine.state
        changed_state = False
        if previous_state in (State.IDLE, State.COMPLETED, State.FINALIZING):
            changed_state = state_machine.try_set(State.UPLOADING, detail=f"enviando {path.name}")

        try:
            if not path.exists():
                raise drive.DriveError(f"arquivo local ausente: {path}")
            result = drive.upload_file(
                path,
                folder_id=str(self.cfg.get("drive.folder_id", "")),
                folder_name=str(self.cfg.get("drive.folder_name", "Pregacoes")),
                progress=lambda pct, total: bus.publish(
                    "upload_progress", {"file": path.name, "percent": pct}
                ),
            )
        except Exception as exc:  # noqa: BLE001
            attempts += 1
            delay = BACKOFF[min(attempts - 1, len(BACKOFF) - 1)]
            self.last_error = str(exc)
            self.db.update_upload(
                upload_id,
                status="PENDING",
                attempts=attempts,
                next_attempt=time.time() + delay,
                error=str(exc),
            )
            log.warning("upload falhou (tentativa %d): %s; proxima em %ds", attempts, exc, delay)
            notify(
                # UPLOAD_FAILED do roteiro: o arquivo continua PENDING na fila
                # e sera tentado de novo. `upload_pendente` continua sendo o
                # aviso de "ha coisas na fila" (ex.: Drive desconectado).
                "upload_falho",
                f"Falha ao enviar {path.name}: {exc}. Nova tentativa em {delay}s.",
                level="warning",
                payload={
                    "attempts": attempts,
                    "file": path.name,
                    "retry_in": delay,
                    "error": str(exc),
                },
            )
            if changed_state and state_machine.state == State.UPLOADING:
                state_machine.try_set(previous_state, detail="")
            return

        size = int(result.get("bytes") or 0)
        self.db.update_upload(
            upload_id,
            status="DONE",
            drive_file_id=result["file_id"],
            drive_path=result["drive_path"],
            bytes=size,
            error=None,
            next_attempt=0,
        )
        session = self.db.get_session(item["session_id"])
        if session:
            self.db.update_session(
                session["id"],
                drive_file_id=result["file_id"],
                drive_path=result["drive_path"],
                state="COMPLETED",
                final_bytes=session.get("final_bytes") or size,
            )
        self.last_result = {
            "file": path.name,
            "file_id": result["file_id"],
            "path": result["drive_path"],
            "bytes": size,
            "ts": time.time(),
        }
        self.last_error = None
        notify(
            "upload_concluido",
            f"{path.name} enviado e confirmado no Google Drive",
            level="success",
            payload=self.last_result,
        )
        self._maybe_delete_local(path)
        if state_machine.state == State.UPLOADING:
            state_machine.try_set(State.COMPLETED, detail="upload concluido")

    def _maybe_delete_local(self, path: Path) -> None:
        if self.cfg.get("drive.keep_local", True):
            return
        try:
            path.unlink()
            log.info("copia local removida apos upload: %s", path)
        except OSError as exc:
            log.warning("nao foi possivel remover %s: %s", path, exc)

    # ------------------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        stats = self.db.upload_stats()
        latest = self.db.list_uploads(limit=1)
        return {
            "pending": stats.get("PENDING", 0),
            "done": stats.get("DONE", 0),
            "failed": stats.get("FAILED", 0),
            "running": stats.get("RUNNING", 0),
            "online": self.online,
            "last_error": self.last_error,
            "last_upload": self.last_result,
            "last_file": latest[0] if latest else None,
        }
