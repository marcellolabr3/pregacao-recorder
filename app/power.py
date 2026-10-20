"""Desliga o Windows somente depois que todas as filas do projeto esvaziam."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Any

from .config import config
from .db import db
from .logging_setup import get
from .states import State, state_machine

log = get("power")


class ShutdownController:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._armed = False
        self._deadline: float | None = None
        self._triggered = False
        self._error = ""

    def _enabled(self) -> bool:
        return bool(config.get("power.shutdown_after_tasks", False))

    def _delay(self) -> int:
        return int(config.get("power.shutdown_delay_minutes", 30) or 30)

    def busy_reasons(self) -> list[str]:
        reasons: list[str] = []
        state = state_machine.state
        if state in (State.RECORDING, State.FINALIZING, State.UPLOADING, State.RECOVERY_REQUIRED):
            reasons.append("gravacao/finalizacao")
        jobs = db.job_contagens()
        if sum(jobs.get(key, 0) for key in ("PENDENTE", "EXECUTANDO", "AGUARDANDO_INTERVENCAO")):
            reasons.append("estudos pendentes")
        uploads = db.upload_stats()
        if uploads.get("PENDING", 0) or uploads.get("RUNNING", 0):
            reasons.append("uploads pendentes")
        if db.pending_whatsapp_sends():
            reasons.append("reenvios WhatsApp pendentes")
        return reasons

    def tick(self, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        with self._lock:
            enabled = self._enabled()
            reasons = self.busy_reasons()
            if not enabled:
                self._armed = False
                self._deadline = None
                self._error = ""
            elif reasons:
                # Uma nova atividade cancela a contagem; o proximo periodo
                # ocioso recebe o atraso inteiro novamente.
                self._armed = True
                self._deadline = None
            elif self._armed and self._deadline is None:
                self._deadline = now + self._delay() * 60
            if enabled and self._deadline is not None and now >= self._deadline and not self._triggered:
                # Contagem no proprio processo: o Windows so recebe o comando
                # apos uma ultima leitura das filas. Nunca agenda no boot ocioso.
                if os.name != "nt":
                    self._error = "Desligamento automatico disponivel apenas no Windows"
                else:
                    try:
                        proc = subprocess.run(
                            ["shutdown.exe", "/s", "/t", "0"],
                            capture_output=True, text=True, timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                        if proc.returncode:
                            self._error = (proc.stderr or "Falha ao desligar Windows").strip()[:240]
                        else:
                            self._triggered = True
                            log.info("desligamento automatico solicitado apos tarefas concluidas")
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        self._error = str(exc)[:240]
                self._armed = False
                self._deadline = None
            return self._status_unlocked(now, reasons)

    def _status_unlocked(self, now: float, reasons: list[str]) -> dict[str, Any]:
        enabled = self._enabled()
        state = ("desabilitado" if not enabled else
                 "desligando" if self._triggered else
                 "erro" if self._error else
                 "aguardando_tarefas" if reasons and self._armed else
                 "contagem" if self._deadline else "aguardando_atividade")
        return {
            "enabled": enabled, "delay_minutes": self._delay(), "state": state,
            "deadline": self._deadline,
            "remaining_seconds": max(0, int(self._deadline - now)) if self._deadline else None,
            "busy_reasons": reasons, "error": self._error,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self._status_unlocked(time.time(), self.busy_reasons())

    def arm(self) -> dict[str, Any]:
        if not self._enabled():
            raise ValueError("Ative o desligamento e salve a CONFIG primeiro")
        with self._lock:
            self._armed = True
            self._deadline = None
            self._error = ""
            self._triggered = False
        return self.tick()

    def cancel(self) -> dict[str, Any]:
        with self._lock:
            self._armed = False
            self._deadline = None
            self._error = ""
        return self.status()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._loop, name="power-monitor", daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while True:
            try:
                self.tick()
            except Exception:
                log.exception("falha no monitor de desligamento")
            time.sleep(2)


controller = ShutdownController()
