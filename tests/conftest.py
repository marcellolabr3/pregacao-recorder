"""Configura os testes: PREGACAO_HOME aponta para um diretorio temporario."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Precisa acontecer ANTES de qualquer import de app.*
_HOME = Path(tempfile.mkdtemp(prefix="pregacao-test-"))
os.environ["PREGACAO_HOME"] = str(_HOME)
os.environ.setdefault("PREGACAO_PIN", "1234")
os.environ.setdefault("PREGACAO_SECRET", "segredo-de-teste")
os.environ.setdefault("PREGACAO_LOG_LEVEL", "WARNING")


@pytest.fixture(scope="session", autouse=True)
def _home():
    _HOME.mkdir(parents=True, exist_ok=True)
    default_cfg = ROOT / "config" / "default.json"
    if default_cfg.exists():
        ( _HOME / "config").mkdir(parents=True, exist_ok=True)
        shutil.copy(default_cfg, _HOME / "config" / "default.json")
    yield _HOME
    shutil.rmtree(_HOME, ignore_errors=True)


def _backup(path: Path):
    return path.read_text(encoding="utf-8") if path.exists() else None


@pytest.fixture(autouse=True)
def _isolate_config():
    """Garante que gravacoes de config feitas por um teste nao vazem para outros."""
    from app.config import config

    targets = [config.user_file, config.defaults_file]
    backups = {t: _backup(t) for t in targets}
    for path, content in backups.items():
        if content is None and path.exists():
            path.unlink()
    config.reload()
    yield
    for path, content in backups.items():
        if content is None:
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    config.reload()


@pytest.fixture()
def home() -> Path:
    return _HOME


@pytest.fixture()
def fresh_state():
    """Reseta a maquina de estados global entre testes."""
    from app.states import State, state_machine

    state_machine.set(State.IDLE, detail="", force=True)
    yield state_machine
    state_machine.set(State.IDLE, detail="", force=True)


@pytest.fixture()
def database(tmp_path):
    from app.db import Database

    return Database(tmp_path / "test.db")


@pytest.fixture()
def cfg():
    from app.config import config

    config.reload()
    return config


@pytest.fixture()
def recordings_root(cfg, tmp_path):
    """Pasta de gravacoes isolada por teste (nunca a do home compartilhado)."""
    root = tmp_path / "recordings"
    root.mkdir(parents=True, exist_ok=True)
    cfg.set("storage.recordings_dir", str(root))
    yield root
