"""Logs persistentes e legiveis sem monitor conectado.

Arquivos:
    logs/pregacao.log          rotativo, 5 x 5 MB
    logs/pregacao.log.current  (mesmo conteudo, para `pregacao status`)
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from . import paths

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup(level: Optional[str] = None) -> logging.Logger:
    global _configured
    if _configured:
        return logging.getLogger("pregacao")

    paths.ensure_layout()
    log_level = (
        level
        or os.environ.get("PREGACAO_LOG_LEVEL", "INFO")
        or "INFO"
    ).upper()

    root = logging.getLogger("pregacao")
    root.setLevel(getattr(logging, log_level, logging.INFO))
    root.propagate = False

    formatter = logging.Formatter(FORMAT, datefmt=DATEFMT)

    # PREGACAO_LOG_FILE permite que outro processo do mesmo projeto (o agente
    # de controle remoto) escreva num arquivo proprio: dois handlers
    # rotativos apontando para o mesmo arquivo perdem a rotacao.
    log_name = (os.environ.get("PREGACAO_LOG_FILE", "") or "pregacao.log").strip()
    log_name = log_name if log_name.endswith(".log") else "pregacao.log"
    file_handler = RotatingFileHandler(
        paths.logs_dir() / log_name,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    _configured = True
    root.info("logging iniciado (nivel=%s, dir=%s)", log_level, paths.logs_dir())
    return root


def get(name: str) -> logging.Logger:
    return logging.getLogger(f"pregacao.{name}")
