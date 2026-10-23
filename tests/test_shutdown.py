"""O desinstalador so encerra processos quando as filas estao ociosas."""
import sqlite3
from types import SimpleNamespace

import pytest

from app import shutdown
from app.shutdown import pending_work


def test_pending_work_blocks_only_running_tasks(tmp_path):
    database = tmp_path / "pregacao.db"
    with sqlite3.connect(database) as conn:
        conn.executescript("""
            CREATE TABLE sessions (state TEXT);
            CREATE TABLE uploads (status TEXT);
            CREATE TABLE jobs (estado TEXT);
            CREATE TABLE whatsapp_sends (status TEXT);
            INSERT INTO sessions VALUES ('COMPLETED');
            INSERT INTO uploads VALUES ('DONE');
            INSERT INTO jobs VALUES ('CONCLUIDO');
            INSERT INTO whatsapp_sends VALUES ('ENVIADO');
        """)
    assert pending_work(database) is False
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO jobs VALUES ('AGUARDANDO_INTERVENCAO')")
    assert pending_work(database) is False
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO jobs VALUES ('EXECUTANDO')")
    assert pending_work(database) is True


@pytest.mark.parametrize("code,status", [
    (0, {}),
    (401, {}),
    (200, {"device_id": "outro-equipamento", "state": "IDLE"}),
])
def test_shutdown_requires_verified_local_status(monkeypatch, tmp_path, code, status):
    monkeypatch.setenv("PREGACAO_HOME", str(tmp_path))
    monkeypatch.setattr(shutdown.bundled_runtime, "prepare_environment", lambda **_kwargs: None)
    monkeypatch.setattr(shutdown, "load_env", lambda _path: None)
    monkeypatch.setattr(shutdown, "Config", lambda _home: SimpleNamespace(
        host="127.0.0.1", port=8080, pin="", device_id="este-equipamento"))
    monkeypatch.setattr(shutdown.launcher, "running_pid",
                        lambda _path, component, _root, _home: 4321 if component == "gravador" else None)
    monkeypatch.setattr(shutdown, "pending_work", lambda _path: False)
    monkeypatch.setattr(shutdown, "LocalApi", lambda *_args, **_kwargs: SimpleNamespace(
        status=lambda: (code, status)))
    monkeypatch.setattr(shutdown.subprocess, "run",
                        lambda *_args, **_kwargs: pytest.fail("processo encerrado sem estado confirmado"))

    assert shutdown.stop() == 4
