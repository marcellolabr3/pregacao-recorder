"""A copia pessoal conserva o estado e acompanha a letra/pasta do SSD."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from app.portable_state import relocate


def _package(root: Path, origin: Path) -> Path:
    for relative in ("gravador/config", "gravador/data", "gravador/recordings",
                     "pipeline/logs", "runtime/python"):
        (root / relative).mkdir(parents=True)
    (root / "portable-state.json").write_text(json.dumps({
        "schema_version": 1,
        "source_roots": {
            "recorder": str(origin),
            "recordings": str(origin / "recordings"),
            "pipeline": str(origin / "external-pipeline"),
            "notebooklm": str(origin / "notebooklm"),
        },
    }), encoding="utf-8")
    (root / "gravador/config/config.json").write_text(json.dumps({
        "device_name": "Meu gravador",
        "storage": {"recordings_dir": str(origin / "recordings")},
        "estudos": {"pasta": str(origin / "external-pipeline"),
                    "python": str(origin / ".venv/Scripts/python.exe")},
        "drive": {"client_secret": "segredo-sintetico"},
    }), encoding="utf-8")
    (root / "gravador/.env").write_text(
        "PREGACAO_DEVICE_ID=meu-id\nPREGACAO_REMOTE_PASSWORD=senha-sintetica\n",
        encoding="utf-8")
    (root / "gravador/recordings/audio.mp3").write_bytes(b"audio-teste")
    (root / "pipeline/logs/resultado.md").write_text("estudo-teste", encoding="utf-8")
    with sqlite3.connect(root / "gravador/data/pregacao.db") as db:
        db.execute("CREATE TABLE sessions (final_path TEXT)")
        db.execute("CREATE TABLE uploads (file_path TEXT)")
        db.execute("CREATE TABLE jobs (audio_path TEXT, resultado TEXT)")
        audio = str(origin / "recordings/audio.mp3")
        db.execute("INSERT INTO sessions VALUES (?)", (audio,))
        db.execute("INSERT INTO uploads VALUES (?)", (audio,))
        db.execute("INSERT INTO jobs VALUES (?, ?)",
                   (audio, str(origin / "external-pipeline/logs/resultado.md")))
    return root


def _paths(root: Path) -> list[str]:
    with sqlite3.connect(root / "gravador/data/pregacao.db") as db:
        return [db.execute("SELECT final_path FROM sessions").fetchone()[0],
                db.execute("SELECT file_path FROM uploads").fetchone()[0],
                *db.execute("SELECT audio_path, resultado FROM jobs").fetchone()]


def test_importar_e_mover_pacote_preserva_dados_credenciais_e_links(tmp_path):
    origin = tmp_path / "maquina de origem"
    first = _package(tmp_path / "SSD A/Pregacao Recorder", origin)
    env_before = (first / "gravador/.env").read_bytes()

    assert relocate(first)
    settings = json.loads((first / "gravador/config/config.json").read_text(encoding="utf-8"))
    assert settings["storage"]["recordings_dir"] == str(first / "gravador/recordings")
    assert settings["estudos"]["pasta"] == str(first / "pipeline")
    assert settings["estudos"]["python"] == str(first / "runtime/python/python.exe")
    assert settings["drive"]["client_secret"] == "segredo-sintetico"
    assert _paths(first) == [str(first / "gravador/recordings/audio.mp3")] * 3 + [
        str(first / "pipeline/logs/resultado.md")]
    assert relocate(first)

    second = tmp_path / "SSD B/Pregacao Recorder"
    shutil.copytree(first, second)
    assert relocate(second)
    assert _paths(second) == [str(second / "gravador/recordings/audio.mp3")] * 3 + [
        str(second / "pipeline/logs/resultado.md")]
    assert (second / "gravador/.env").read_bytes() == env_before
    assert (second / "gravador/recordings/audio.mp3").read_bytes() == b"audio-teste"
    assert json.loads((second / "portable-state.json").read_text(encoding="utf-8"))["last_root"] == str(second)


def test_destino_de_gravacao_alheio_ao_pacote_nao_e_silenciosamente_trocado(tmp_path):
    root = _package(tmp_path / "SSD/Pregacao Recorder", tmp_path / "origem")
    target = root / "gravador/config/config.json"
    settings = json.loads(target.read_text(encoding="utf-8"))
    settings["storage"]["recordings_dir"] = str(tmp_path / "outra unidade")
    target.write_text(json.dumps(settings), encoding="utf-8")
    with pytest.raises(ValueError, match="externo ao SSD"):
        relocate(root)
    assert "last_root" not in json.loads((root / "portable-state.json").read_text(encoding="utf-8"))


def test_pacote_publico_sem_marcador_nao_e_modificado(tmp_path):
    assert relocate(tmp_path) is False
