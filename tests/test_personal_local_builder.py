"""A instalacao local deve levar o estado ativo do SSD sem depender dele."""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from app.portable_state import relocate


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def source_package(tmp_path):
    source = tmp_path / "SSD de teste" / "PregacaoRecorder-Pessoal"
    files = {}
    for relative in (
        "Iniciar Pregacao.cmd", "Verificar Pacote.cmd",
        "gravador/app/launcher.py", "gravador/config/default.json",
        "runtime/python/python.exe",
    ):
        file = source / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"public-fixture")
        files[relative] = hashlib.sha256(file.read_bytes()).hexdigest()
    (source / "package-manifest.json").write_text(json.dumps({
        "schema_version": 1, "name": "PregacaoRecorder",
        "version": "update-test", "personal_portable": True,
        "update_only": True, "files": files,
    }), encoding="utf-8")
    (source / "personal-manifest.json").write_text(
        json.dumps({"schema_version": 1, "files": {}}), encoding="utf-8")
    (source / "portable-state.json").write_text(json.dumps({
        "schema_version": 1, "source_roots": {
            "recorder": str(tmp_path / "origem" / "gravador"),
            "recordings": str(tmp_path / "origem" / "gravador" / "recordings"),
            "pipeline": str(tmp_path / "origem" / "pipeline"),
            "notebooklm": str(tmp_path / "origem" / "notebooklm"),
        }, "last_root": str(source),
    }), encoding="utf-8")
    (source / "gravador/config/config.json").write_text(json.dumps({
        "storage": {"recordings_dir": str(source / "gravador/recordings")},
        "estudos": {"pasta": str(source / "pipeline")},
    }), encoding="utf-8")
    (source / "gravador/.env").write_bytes(b"PREGACAO_SECRET=segredo-sintetico\n")
    recording = source / "gravador/recordings/audio.mp3"
    recording.parent.mkdir(parents=True)
    recording.write_bytes(b"audio-sintetico")
    auth = source / "pipeline/whatsapp/auth/creds.json"
    auth.parent.mkdir(parents=True)
    auth.write_bytes(b"credencial-sintetica")
    notebook = source / "gravador/data/notebooklm/state.json"
    notebook.parent.mkdir(parents=True)
    notebook.write_bytes(b"perfil-sintetico")
    backup = source / "gravador/recovery/update-antigo/runtime/old.bin"
    backup.parent.mkdir(parents=True)
    backup.write_bytes(b"backup-redundante")
    apk = source / "PregacaoControle-2.7.apk"
    apk.write_bytes(b"apk-atual")
    (source / "PregacaoControle-2.6.apk").write_bytes(b"apk-antigo")
    db_path = source / "gravador/data/pregacao.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE sessions (state TEXT, final_path TEXT)")
        db.execute("CREATE TABLE uploads (status TEXT, file_path TEXT)")
        db.execute("CREATE TABLE jobs (estado TEXT, audio_path TEXT, resultado TEXT)")
        db.execute("CREATE TABLE whatsapp_sends (status TEXT)")
        db.execute("INSERT INTO sessions VALUES (?, ?)", ("COMPLETED", str(recording)))
        db.execute("INSERT INTO uploads VALUES (?, ?)", ("DONE", str(recording)))
        db.execute("INSERT INTO jobs VALUES (?, ?, ?)",
                   ("ERRO", str(recording), str(source / "pipeline/output/estudo.pdf")))
    return source, apk


def test_local_snapshot_preserves_active_state_and_relocates_without_ssd(
    source_package, tmp_path, monkeypatch,
):
    monkeypatch.syspath_prepend(str(ROOT / "packaging"))
    builder = importlib.import_module("build_personal_local")
    source, apk = source_package
    stage = tmp_path / "instalacao local"

    public, private = builder.prepare_snapshot(source, stage, "local-test", apk)

    assert "PregacaoControle-2.7.apk" in private
    assert "PregacaoControle-2.6.apk" not in private
    assert not (stage / "gravador/recovery/update-antigo").exists()
    assert (stage / "gravador/.env").read_bytes() == (source / "gravador/.env").read_bytes()
    assert (stage / "pipeline/whatsapp/auth/creds.json").read_bytes() == b"credencial-sintetica"
    assert (stage / "gravador/data/notebooklm/state.json").read_bytes() == b"perfil-sintetico"
    assert (stage / "gravador/recordings/audio.mp3").read_bytes() == b"audio-sintetico"
    assert "package-manifest.json" in public
    assert json.loads((stage / "package-manifest.json").read_text())["local_install"]

    assert relocate(stage)
    config = json.loads((stage / "gravador/config/config.json").read_text())
    assert config["storage"]["recordings_dir"] == str(stage / "gravador/recordings")
    assert config["estudos"]["pasta"] == str(stage / "pipeline")
    with sqlite3.connect(stage / "gravador/data/pregacao.db") as db:
        assert db.execute("SELECT final_path FROM sessions").fetchone()[0] == str(
            stage / "gravador/recordings/audio.mp3")
        assert db.execute("SELECT resultado FROM jobs").fetchone()[0] == str(
            stage / "pipeline/output/estudo.pdf")


def test_local_snapshot_rejects_work_in_progress(source_package, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "packaging"))
    builder = importlib.import_module("build_personal_local")
    source, apk = source_package
    with sqlite3.connect(source / "gravador/data/pregacao.db") as db:
        db.execute("UPDATE jobs SET estado = 'PENDENTE'")
    with pytest.raises(RuntimeError, match="tarefas em andamento"):
        builder.prepare_snapshot(source, tmp_path / "destino", "local-test", apk)


def test_local_snapshot_uses_matching_validated_public_bundle(
    source_package, tmp_path, monkeypatch,
):
    monkeypatch.syspath_prepend(str(ROOT / "packaging"))
    builder = importlib.import_module("build_personal_local")
    source, apk = source_package
    base = tmp_path / "pacote publico"
    shutil.copytree(source, base)
    (source / "runtime/python/python.exe").unlink()

    stage = tmp_path / "local completo"
    builder.prepare_snapshot(source, stage, "local-test", apk, base=base)

    assert (stage / "runtime/python/python.exe").read_bytes() == b"public-fixture"
    assert (stage / "gravador/recordings/audio.mp3").read_bytes() == b"audio-sintetico"
