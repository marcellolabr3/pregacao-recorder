"""Notificacoes: banco + log + push SSE para a interface web (um unico ponto)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from . import db as _db_module
from .events import bus
from .logging_setup import get

log = get("notify")
LEVELS = {"info", "warning", "error", "success"}


def notify(
    kind: str,
    message: str,
    level: str = "info",
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    level = level if level in LEVELS else "info"
    log.log(
        {"info": 20, "success": 20, "warning": 30, "error": 40}[level],
        "%s: %s",
        kind,
        message,
    )
    try:
        _db_module.db.add_event(level, kind, message, payload)
    except Exception:  # pragma: no cover - log nunca pode derrubar o servico
        log.exception("falha ao gravar evento no banco")
    data = {"message": message, "level": level, **(payload or {})}
    return bus.publish(kind, data)
