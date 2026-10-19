"""Orquestracao da gravacao: iniciar, finalizar, consolidar, recuperar.

Este e o unico modulo autorizado a transicionar o estado global. A interface
web apenas pede; quem decide e o PC.
"""
from __future__ import annotations

import shutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..audio import device as audio_device
from ..audio import wav
from ..audio.recorder import SegmentRecorder
from ..config import Config
from ..db import Database
from ..logging_setup import get
from ..notify import notify
from ..states import State, state_machine
from ..storage import destinos, layout
from ..upload import queue as upload_queue
from . import consolidate, recovery
from .. import estudos, paths

log = get("manager")


class ManagerError(RuntimeError):
    """Erro que a API pode devolver com mensagem amigavel."""


class RecordingManager:
    def __init__(self, cfg: Config, database: Database,
                 uploader: Optional[upload_queue.UploadWorker] = None) -> None:
        self.cfg = cfg
        self.db = database
        self.uploader = uploader
        self.recorder: Optional[SegmentRecorder] = None
        self.device: Dict[str, Any] = {}
        self.session_id: Optional[str] = None
        self._finalizing: set = set()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # propriedades basicas
    # ------------------------------------------------------------------
    @property
    def root(self) -> Path:
        return self.cfg.recordings_root

    @property
    def auto_upload(self) -> bool:
        return bool(self.cfg.get("drive.auto_upload", True))

    # ------------------------------------------------------------------
    # estado
    # ------------------------------------------------------------------
    def start(self) -> Dict[str, Any]:
        state = state_machine.state
        if state == State.RECORDING:
            raise ManagerError("ja existe uma gravacao em andamento.")
        if state == State.RECOVERY_REQUIRED:
            raise ManagerError(
                "Existe uma gravacao interrompida pendente. "
                "Recupere ou descarte antes de iniciar uma nova."
            )
        if state in (State.FINALIZING, State.UPLOADING):
            raise ManagerError("Aguarde: o sistema esta finalizando/enviando uma gravacao.")
        if state not in (State.IDLE, State.COMPLETED, State.ERROR):
            raise ManagerError(f"Estado {state} nao permite iniciar gravacao.")

        with self._lock:
            if self.recorder and self.recorder.running:
                raise ManagerError("ja existe uma gravacao em andamento.")

            # dispositivo de audio
            configured = str(self.cfg.get("audio.device", "auto"))
            self.device = audio_device.detect(configured)
            if self.device.get("selected_by") == "fallback" and self.device.get("card", -1) == -1:
                state_machine.try_set(State.ERROR, detail="nenhuma interface de audio")
                raise ManagerError(
                    "Nenhuma interface de audio encontrada. "
                    "Verifique a interface USB (veja docs/AUDIO.md)."
                )

            # Nunca trocar silenciosamente o volume configurado.
            aviso_destino = destinos.aviso(self.root, paths.recordings_dir())
            if aviso_destino:
                raise ManagerError(aviso_destino)

            # espaco em disco
            min_free = int(self.cfg.get("storage.min_free_mb", 512))
            usage = layout.disk_usage(self.root)
            if usage.get("ok") and usage["free_mb"] < min_free:
                state_machine.try_set(State.ERROR, detail="espaco insuficiente")
                raise ManagerError(
                    f"Espaco insuficiente no armazenamento "
                    f"({usage['free_mb']} MB livres, minimo {min_free} MB)."
                )

            session_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
            session_dir = self.root / ".sessions" / session_id
            rate = int(self.cfg.get("audio.sample_rate", 44100))
            channels = int(self.cfg.get("audio.channels", 2))
            fmt = str(self.cfg.get("audio.format", "S16_LE"))

            session_dir.mkdir(parents=True, exist_ok=True)
            self.db.create_session(
                {
                    "id": session_id,
                    "started_at": time.time(),
                    "state": State.RECORDING,
                    "device": self.device.get("hw"),
                    "format": fmt,
                    "sample_rate": rate,
                    "channels": channels,
                }
            )
            recovery.write_meta(
                session_dir,
                {
                    "session_id": session_id,
                    "started_at": time.time(),
                    "device": self.device.get("hw"),
                    "device_name": self.device.get("name"),
                    "format": fmt,
                    "sample_rate": rate,
                    "channels": channels,
                    "segment_seconds": self.cfg.get("audio.segment_seconds", 60),
                },
            )

            recorder = SegmentRecorder(
                session_dir=session_dir,
                device=str(self.device.get("hw", "default")),
                sample_fmt=fmt,
                sample_rate=rate,
                channels=channels,
                segment_seconds=int(self.cfg.get("audio.segment_seconds", 60)),
                on_event=self._on_recorder_event,
            )
            state_machine.set(State.RECORDING, detail="gravando", session_id=session_id)
            recorder.start()
            self.recorder = recorder
            self.session_id = session_id

        notify(
            "gravacao_iniciada",
            "Gravacao iniciada",
            level="success",
            payload={
                "session_id": session_id,
                "device": self.device.get("name"),
                "started_at": time.time(),
            },
        )
        log.info(
            "gravacao iniciada: session=%s device=%s(%s) rate=%d ch=%d",
            session_id, self.device.get("hw"), self.device.get("name"), rate, channels,
        )
        return {"session_id": session_id, "device": self.device}

    def stop(self) -> Dict[str, Any]:
        state_machine.require(State.RECORDING)
        with self._lock:
            recorder = self.recorder
            if recorder is None:
                state_machine.try_set(State.IDLE, detail="")
                raise ManagerError("Nenhuma gravacao ativa.")
            session_id = self.session_id
            self.recorder = None

        state_machine.set(State.FINALIZING, detail="consolidando segmentos", session_id=session_id)
        recorder.stop()
        recorder.finalize_headers()

        progress = recorder.progress()
        self.db.update_session(
            session_id,
            segments=progress["segments"],
            bytes=progress["bytes"],
            duration_secs=progress["duration"],
        )
        notify(
            "gravacao_finalizada",
            "Gravacao finalizada; consolidando arquivos",
            level="info",
            payload={"session_id": session_id, "duration": progress["duration"]},
        )
        threading.Thread(
            target=self._finalize,
            args=(session_id, False),
            name="finalize",
            daemon=True,
        ).start()
        return {"session_id": session_id, "segments": progress["segments"]}

    # ------------------------------------------------------------------
    # consolidacao / recuperacao
    # ------------------------------------------------------------------
    def _finalize(self, session_id: str, interrupted: bool) -> None:
        with self._lock:
            if session_id in self._finalizing:
                return
            self._finalizing.add(session_id)
        try:
            self._finalize_inner(session_id, interrupted)
        except Exception as exc:  # noqa: BLE001
            log.exception("falha ao finalizar sessao %s", session_id)
            # os segmentos continuam no disco: volta para a fila de recuperacao
            # para que o usuario possa tentar de novo em vez de perder o audio.
            session_dir = self.root / ".sessions" / session_id
            if consolidate.segment_list(session_dir):
                self.db.update_session(
                    session_id,
                    state=State.RECOVERY_REQUIRED,
                    error=str(exc),
                    interrupted=1,
                )
                state_machine.try_set(State.RECOVERY_REQUIRED, detail=str(exc))
                notify(
                    "erro",
                    f"Falha ao consolidar a gravacao; segmentos preservados: {exc}",
                    level="error",
                    payload={"session_id": session_id},
                )
            else:
                self.db.update_session(session_id, state=State.ERROR, error=str(exc))
                state_machine.try_set(State.ERROR, detail=str(exc))
                notify("erro", f"Falha ao finalizar a gravacao: {exc}", level="error")
        finally:
            with self._lock:
                self._finalizing.discard(session_id)

    def _finalize_inner(self, session_id: str, interrupted: bool) -> None:
        session = self.db.get_session(session_id)
        if not session:
            raise ManagerError(f"sessao {session_id} nao encontrada")
        session_dir = self.root / ".sessions" / session_id
        segments = consolidate.segment_list(session_dir)
        if segments:
            recovery.repair_segments(
                session_dir,
                int(session.get("sample_rate") or 44100),
                int(session.get("channels") or 2),
            )
            segments = consolidate.segment_list(session_dir)

        if not segments:
            # nada foi capturado (finalizacao quase imediata, 0 bytes).
            # Isso nao e' uma falha do sistema: descarta a sessao vazia,
            # avisa o usuario e devolve o sistema para PRONTO.
            shutil.rmtree(session_dir, ignore_errors=True)
            self.db.delete_session(session_id)
            state_machine.try_set(State.IDLE, detail="")
            notify(
                "gravacao_vazia",
                "Gravacao vazia descartada - nenhum audio foi capturado",
                level="warning",
                payload={"session_id": session_id},
            )
            return

        started_at = float(session.get("started_at") or time.time())
        encoder = str(self.cfg.get("audio.encoder", "mp3"))
        target = layout.final_path(self.root, started_at, ".mp3" if encoder == "mp3" else ".wav")

        notify(
            "conversao",
            f"Consolidando {len(segments)} segmento(s) em {target.name}",
            level="info",
        )
        result = consolidate.consolidate(
            segments,
            target,
            sample_rate=int(session.get("sample_rate") or 44100),
            channels=int(session.get("channels") or 2),
            encoder=encoder,
            bitrate=int(self.cfg.get("audio.bitrate", 128)),
        )

        check = consolidate.verify(result["path"])
        if not check.get("ok"):
            raise ManagerError(f"verificacao do arquivo falhou: {check.get('error')}")

        duration = self._duration_of(result["path"], session)
        self.db.update_session(
            session_id,
            state="COMPLETED",
            final_path=str(result["path"]),
            final_bytes=result["bytes"],
            duration_secs=duration,
            interrupted=1 if interrupted else 0,
            error=None,  # sucesso limpa qualquer erro anterior
        )

        # Segmentos so agora podem ser removidos: a conversao foi confirmada.
        removed = consolidate.cleanup_segments(session_dir)
        try:
            if session_dir.exists():
                for extra in session_dir.glob("*"):
                    extra.unlink()
                session_dir.rmdir()
        except OSError:
            pass
        log.info("segmentos removidos apos consolidacao: %d", removed)

        layout.prune(self.root, int(self.cfg.get("storage.retention_days", 0)))

        notify(
            "gravacao_pronta",
            f"Gravacao salva: {result['path'].name} ({result['bytes']} bytes, {duration:.0f}s)",
            level="success",
            payload={
                "session_id": session_id,
                "path": str(result["path"]),
                "bytes": result["bytes"],
                "duration": duration,
                "interrupted": interrupted,
            },
        )

        # estudo devocional (NotebookLM -> PDF -> WhatsApp): fila propria,
        # roda em paralelo ao upload e so se "estudos" estiver configurado
        estudos.enfileirar(str(result["path"]))

        should_upload = self.auto_upload and bool(self.cfg.get("drive.enabled", True))
        if should_upload:
            # O estado UPLOADING so e assumido enquanto o envio realmente
            # acontece. Enquanto a fila aguarda internet/Drive, o sistema fica
            # COMPLETED para permitir iniciar a proxima pregação.
            self.db.enqueue_upload(session_id, str(result["path"]), result["bytes"])
            state_machine.try_set(
                State.COMPLETED, detail="gravacao salva; upload na fila"
            )
            if self.uploader:
                self.uploader.kick()
        else:
            state_machine.try_set(State.COMPLETED, detail="gravacao concluida")

    def recover(self, session_id: str) -> Dict[str, Any]:
        session = self.db.get_session(session_id)
        if not session:
            raise ManagerError("Gravacao interrompida nao encontrada.")
        if session["state"] != State.RECOVERY_REQUIRED:
            raise ManagerError(f"Estado {session['state']} nao permite recuperacao.")
        state_machine.set(State.FINALIZING, detail="recuperando gravacao", session_id=session_id)
        notify(
            "recuperacao",
            "Recuperando gravacao interrompida...",
            level="warning",
            payload={"session_id": session_id},
        )
        threading.Thread(
            target=self._finalize, args=(session_id, True), name="recover", daemon=True
        ).start()
        return {"session_id": session_id, "status": "FINALIZING"}

    def discard(self, session_id: str) -> Dict[str, Any]:
        session = self.db.get_session(session_id)
        if not session:
            raise ManagerError("Gravacao interrompida nao encontrada.")
        if session["state"] != State.RECOVERY_REQUIRED:
            raise ManagerError(f"Estado {session['state']} nao permite descartar.")
        recovery.discard(self.db, session_id, self.root)
        state_machine.try_set(State.IDLE, detail="")
        notify(
            "recuperacao_descartada",
            "Gravacao interrompida descartada pelo usuario",
            level="warning",
            payload={"session_id": session_id},
        )
        return {"session_id": session_id, "status": "DISCARDED"}

    def pending_recovery(self) -> List[Dict[str, Any]]:
        out = []
        for sess in recovery.pending(self.db):
            session_dir = self.root / ".sessions" / sess["id"]
            info = recovery.repair_segments(
                session_dir,
                int(sess.get("sample_rate") or 44100),
                int(sess.get("channels") or 2),
            )
            out.append(
                {
                    "id": sess["id"],
                    "started_at": sess["started_at"],
                    "started_label": datetime.fromtimestamp(sess["started_at"]).strftime(
                        "%d/%m/%Y %H:%M:%S"
                    ),
                    "duration": info["duration"],
                    "bytes": info["bytes"],
                    "segments": info["segments"],
                    "reason": "falha_na_consolidacao" if sess.get("error") else "queda_de_energia",
                    "error": sess.get("error"),
                }
            )
        return out

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    def progress(self) -> Dict[str, Any]:
        recorder = self.recorder
        if not recorder:
            return {"active": False, "duration": 0, "bytes": 0, "segments": 0}
        data = recorder.progress()
        data["active"] = recorder.running
        data["started_at"] = recorder.started_at
        return data

    def last_recording(self) -> Optional[Dict[str, Any]]:
        rows = self.db.list_sessions(limit=1)
        if not rows:
            latest = layout.list_recordings(self.root, limit=1)
            if not latest:
                return None
            item = latest[0]
            return {
                "id": None,
                "final_path": item["path"],
                "final_bytes": item["bytes"],
                "ended_at": item["modified"],
                "state": "COMPLETED",
            }
        return rows[0]

    def status(self) -> Dict[str, Any]:
        recovery_items = self.pending_recovery()

        # O estado global precisa refletir a realidade: se existem gravacoes
        # interrompidas pendentes, o sistema esta em ATENCAO - mesmo que uma
        # tentativa anterior tenha terminado em ERROR.
        current = state_machine.state
        if recovery_items and current not in (
            State.RECORDING,
            State.FINALIZING,
            State.UPLOADING,
            State.RECOVERY_REQUIRED,
        ):
            state_machine.set(
                State.RECOVERY_REQUIRED,
                detail=f"{len(recovery_items)} gravacao(oes) interrompida(s)",
                force=True,
            )

        snap = state_machine.snapshot()
        progress = self.progress()
        usage = layout.disk_usage(self.root)
        uploads = self.uploader.snapshot() if self.uploader else {}
        return {
            "state": snap["state"],
            "since": snap["since"],
            "detail": snap["detail"],
            "session_id": snap["session_id"] or self.session_id,
            "recording": progress,
            "started_at": progress.get("started_at"),
            "device": self.device or None,
            "storage": usage,
            "uploads": uploads,
            "recovery": recovery_items,
            "last_recording": self.last_recording(),
        }

    # ------------------------------------------------------------------
    def _on_recorder_event(self, kind: str, payload: Dict[str, Any]) -> None:
        if kind == "capture_gap":
            notify(
                "capture_gap",
                f"Interface de audio caiu: {payload.get('message')}. Tentando reconectar.",
                level="warning",
                payload=payload,
            )
        elif kind == "error":
            notify("erro", str(payload.get("message")), level="error", payload=payload)

    @staticmethod
    def _duration_of(path: Path, session: Dict[str, Any]) -> float:
        info = wav.read_info(path)
        if info:
            return info["duration"]
        if str(path).lower().endswith(".mp3") and session.get("duration_secs"):
            return float(session["duration_secs"])
        return float(session.get("duration_secs") or 0)
