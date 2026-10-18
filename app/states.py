"""Maquina de estados do sistema de gravacao.

Estados possiveis (nunca coexistem):

    IDLE                nenhuma gravacao em andamento
    RECORDING           captura de audio em andamento
    FINALIZING          consolidando segmentos / convertendo
    UPLOADING           enviando para o Google Drive
    COMPLETED           gravacao pronta (com ou sem upload)
    RECOVERY_REQUIRED   queda de energia detectada, aguardando decisao
    ERROR               falha que impede operar normalmente

Transicoes invalidas lancam ``InvalidTransition`` e NUNCA alteram o estado.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Iterable, Optional


class State:
    IDLE = "IDLE"
    RECORDING = "RECORDING"
    FINALIZING = "FINALIZING"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    ERROR = "ERROR"

    ALL = (IDLE, RECORDING, FINALIZING, UPLOADING, COMPLETED, RECOVERY_REQUIRED, ERROR)


class InvalidTransition(Exception):
    pass


#: Mapa de transicoes permitidas.
TRANSITIONS: Dict[str, Iterable[str]] = {
    State.IDLE: (State.RECORDING, State.RECOVERY_REQUIRED, State.ERROR, State.UPLOADING),
    State.RECORDING: (State.FINALIZING, State.IDLE, State.ERROR, State.RECOVERY_REQUIRED),
    State.FINALIZING: (State.COMPLETED, State.UPLOADING, State.ERROR, State.IDLE),
    State.UPLOADING: (State.COMPLETED, State.ERROR, State.IDLE),
    State.COMPLETED: (
        State.IDLE,
        State.RECORDING,
        State.RECOVERY_REQUIRED,
        State.ERROR,
        State.UPLOADING,
    ),
    State.RECOVERY_REQUIRED: (State.IDLE, State.FINALIZING, State.ERROR),
    State.ERROR: (State.IDLE, State.RECORDING, State.RECOVERY_REQUIRED),
}


def can_transition(current: str, target: str) -> bool:
    if target not in State.ALL:
        return False
    return target in TRANSITIONS.get(current, ())


class SystemState:
    """Fonte de verdade do estado global. Existe apenas no servidor."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = State.IDLE
        self._since = time.time()
        self._detail: str = ""
        self._session_id: Optional[str] = None

    # -- leitura ---------------------------------------------------------
    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def session_id(self) -> Optional[str]:
        with self._lock:
            return self._session_id

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            return {
                "state": self._state,
                "since": self._since,
                "detail": self._detail,
                "session_id": self._session_id,
            }

    # -- escrita ---------------------------------------------------------
    def set(
        self,
        target: str,
        detail: str = "",
        session_id: Optional[str] = None,
        force: bool = False,
    ) -> str:
        """Transiciona o estado. Retorna o estado final."""
        with self._lock:
            if target != self._state and not force and not can_transition(self._state, target):
                raise InvalidTransition(f"{self._state} -> {target}")
            self._state = target
            self._since = time.time()
            self._detail = detail
            if session_id is not None:
                self._session_id = session_id
            return self._state

    def try_set(self, target: str, detail: str = "", session_id: Optional[str] = None) -> bool:
        try:
            self.set(target, detail=detail, session_id=session_id)
            return True
        except InvalidTransition:
            return False

    def require(self, *allowed: str) -> None:
        if self._state not in allowed:
            raise InvalidTransition(
                f"operacao nao permitida no estado {self._state} (esperado: {', '.join(allowed)})"
            )


state_machine = SystemState()
