"""Diretorios do pregacao-recorder.

Todos os caminhos derivam de ``PREGACAO_HOME`` (padrao: /opt/pregacao-recorder).
Isso permite rodar os testes e o modo de desenvolvimento em qualquer maquina.
"""
from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("PREGACAO_HOME", "/opt/pregacao-recorder")).resolve()


def app_dir() -> Path:
    return home() / "app"


def config_dir() -> Path:
    return home() / "config"


def recordings_dir() -> Path:
    return home() / "recordings"


def recovery_dir() -> Path:
    return home() / "recovery"


def logs_dir() -> Path:
    return home() / "logs"


def scripts_dir() -> Path:
    return home() / "scripts"


def systemd_dir() -> Path:
    return home() / "systemd"


def data_dir() -> Path:
    """Banco SQLite e demais dados volateis (nao vai para o microSD se preferir)."""
    return home() / "data"


def db_file() -> Path:
    return data_dir() / "pregacao.db"


def env_file() -> Path:
    return home() / ".env"


def sessions_dir() -> Path:
    """Sessoes ativas (segmentos sendo gravados agora)."""
    return recordings_dir() / ".sessions"


def ensure_layout() -> None:
    for path in (
        home(),
        config_dir(),
        recordings_dir(),
        recovery_dir(),
        logs_dir(),
        data_dir(),
        sessions_dir(),
    ):
        path.mkdir(parents=True, exist_ok=True)
