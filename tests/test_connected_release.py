"""The private edition carries connections without migrating old local data."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def builder(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "packaging"))
    return importlib.import_module("build_connected_release")


@pytest.fixture
def personal_source(tmp_path):
    source = tmp_path / "source"
    (source / "config").mkdir(parents=True)
    (source / "config/config.json").write_text(json.dumps({
        "device_name": "Pulpito",
        "audio": {"device": "old microphone"},
        "storage": {"recordings_dir": "D:/old/recordings"},
        "estudos": {"python": "D:/old/python.exe", "pasta": "D:/old/pipeline"},
        "drive": {"enabled": True, "auto_upload": True, "folder_name": "Pregacoes",
                  "client_id": "client.apps.googleusercontent.com", "client_secret": "google-secret"},
        "remote": {"device_id": "igreja-atual"},
    }), encoding="utf-8")
    (source / "config/google_token.json").write_text(json.dumps({
        "token": "access", "refresh_token": "refresh",
        "client_id": "client.apps.googleusercontent.com", "client_secret": "google-secret",
    }), encoding="utf-8")
    (source / ".env").write_text(
        "PREGACAO_REMOTE_HOST=broker.example\n"
        "PREGACAO_REMOTE_PASSWORD=broker-secret\n"
        "PREGACAO_DEVICE_ID=old-id\n"
        "PREGACAO_OPERATOR_TOKEN=operator-secret\n"
        "PREGACAO_PIPELINE_HOME=D:/old/pipeline\n"
        "NODE_PATH=D:/old/node_modules\n",
        encoding="utf-8",
    )
    return source


def test_overlay_keeps_connections_only(builder, personal_source, tmp_path):
    bundle = tmp_path / "bundle"
    files = builder.prepare_connection_overlay(personal_source, bundle)
    assert files == builder.CONNECTION_FILES
    config = json.loads((bundle / files[0]).read_text(encoding="utf-8"))
    assert config["drive"]["client_secret"] == "google-secret"
    assert config["remote"]["device_id"] == "igreja-atual"
    assert "audio" not in config and "storage" not in config and "estudos" not in config
    assert "setup" not in config
    assert "D:/old" not in json.dumps(config)
    assert json.loads((bundle / files[1]).read_text(encoding="utf-8"))["refresh_token"] == "refresh"
    env = (bundle / files[2]).read_text(encoding="utf-8")
    assert "broker-secret" in env and "operator-secret" in env
    assert "PREGACAO_PIPELINE_HOME" not in env and "NODE_PATH" not in env
    assert not (bundle / "gravador/data").exists()
    assert not (bundle / "gravador/recordings").exists()
    marker = json.loads((bundle / files[3]).read_text(encoding="utf-8"))
    assert marker["last_root"] == str(bundle.resolve())
    assert marker["source_roots"] == {}


def test_first_launch_sets_study_paths_in_new_location(builder, personal_source, tmp_path):
    from app.portable_state import relocate

    bundle = tmp_path / "bundle"
    builder.prepare_connection_overlay(personal_source, bundle)
    installed = tmp_path / "installed"
    (installed / "gravador/config").mkdir(parents=True)
    for rel in ("gravador/config/config.json", "portable-state.json"):
        target = installed / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((bundle / rel).read_bytes())
    assert relocate(installed)
    settings = json.loads((installed / "gravador/config/config.json").read_text(encoding="utf-8"))
    assert settings["estudos"]["pasta"] == str(installed / "pipeline")
    assert settings["estudos"]["python"] == str(installed / "runtime/python/python.exe")
    assert settings["storage"]["recordings_dir"] == str(installed / "gravador/recordings")
    assert settings["drive"]["client_secret"] == "google-secret"
    assert settings["remote"]["device_id"] == "igreja-atual"


def test_mismatched_google_token_rejected(builder, personal_source, tmp_path):
    path = personal_source / "config/google_token.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["client_secret"] = "another-client"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Token Google"):
        builder.prepare_connection_overlay(personal_source, tmp_path / "bundle")


def test_overlay_carries_notebooklm_token_and_current_session(builder, personal_source, tmp_path):
    profile = personal_source / "data/notebooklm/profiles/default"
    profile.mkdir(parents=True)
    token = {"version": 1, "email": "me@example.com", "android_id": "abcdef12",
             "master_token": "private-token"}
    (profile / "master_token.json").write_text(json.dumps(token), encoding="utf-8")
    (profile / "storage_state.json").write_text('{"cookies": ["old"]}', encoding="utf-8")
    (profile / "browser_profile").mkdir()
    bundle = tmp_path / "bundle"

    files = builder.prepare_connection_overlay(personal_source, bundle)

    assert files == (*builder.CONNECTION_FILES, builder.NOTEBOOKLM_TOKEN,
                     builder.NOTEBOOKLM_STORAGE)
    assert json.loads((bundle / builder.NOTEBOOKLM_TOKEN).read_text(encoding="utf-8")) == token
    assert (bundle / builder.NOTEBOOKLM_STORAGE).is_file()
    assert not (bundle / "gravador/data/notebooklm/profiles/default/browser_profile").exists()


def test_invalid_notebooklm_token_rejected(builder, personal_source, tmp_path):
    profile = personal_source / "data/notebooklm/profiles/default"
    profile.mkdir(parents=True)
    (profile / "master_token.json").write_text('{"email":"me@example.com"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Master token"):
        builder.prepare_connection_overlay(personal_source, tmp_path / "bundle")


def test_inno_entries_list_only_the_four_private_files(builder, personal_source, tmp_path):
    bundle = tmp_path / "bundle"
    files = builder.prepare_connection_overlay(personal_source, bundle)
    script = tmp_path / "script/setup.iss"
    script.parent.mkdir()
    script.write_text("[Setup]\n", encoding="utf-8")
    builder.write_private_entries(script, bundle, files)
    entries = (script.parent / "connection-files.iss").read_text(encoding="utf-8-sig")
    assert entries.count("Source:") == 4
    assert "D:/old" not in entries
    assert "#define ConnectedPersonalBuild" in script.read_text(encoding="utf-8-sig")
    assert '#include "connection-files.iss"' in (ROOT / "packaging/installer.iss").read_text(encoding="utf-8")


def test_mobile_defines_use_operator_credential_and_saved_device(builder, personal_source, tmp_path):
    bundle = tmp_path / "bundle"
    builder.prepare_connection_overlay(personal_source, bundle)
    mobile = builder.mobile_defines(bundle)
    assert mobile == {
        "PREGACAO_MOBILE_HOST": "broker.example",
        "PREGACAO_MOBILE_PORT": "8883",
        "PREGACAO_MOBILE_TLS": "true",
        "PREGACAO_MOBILE_DEVICE_ID": "igreja-atual",
        "PREGACAO_MOBILE_USERNAME": "operador",
        "PREGACAO_MOBILE_PASSWORD": "operator-secret",
    }
    assert mobile["PREGACAO_MOBILE_PASSWORD"] != "broker-secret"


def test_overlay_carries_whatsapp_auth_and_recipients(builder, personal_source, tmp_path):
    pipeline = tmp_path / "pipeline"
    auth = pipeline / "whatsapp/auth"
    auth.mkdir(parents=True)
    (auth / "creds.json").write_text('{"auth":"linked"}', encoding="utf-8")
    (auth / "keys").mkdir()
    (auth / "keys/key.json").write_text('{"key":"saved"}', encoding="utf-8")
    env = personal_source / ".env"
    env.write_text(env.read_text(encoding="utf-8").replace(
        "PREGACAO_PIPELINE_HOME=D:/old/pipeline",
        f"PREGACAO_PIPELINE_HOME={pipeline}"), encoding="utf-8")
    settings = personal_source / "config/config.json"
    config = json.loads(settings.read_text(encoding="utf-8"))
    config["estudos"]["whatsapp"] = "5511999999999"
    settings.write_text(json.dumps(config), encoding="utf-8")
    bundle = tmp_path / "bundle"
    files = builder.prepare_connection_overlay(personal_source, bundle)
    assert builder.WHATSAPP_AUTH in files
    assert (bundle / builder.WHATSAPP_AUTH / "keys/key.json").is_file()
    assert json.loads((bundle / builder.CONNECTION_FILES[0]).read_text(
        encoding="utf-8"))["estudos"]["whatsapp"] == "5511999999999"
    script = tmp_path / "script/setup.iss"
    script.parent.mkdir()
    script.write_text("[Setup]\n", encoding="utf-8")
    builder.write_private_entries(script, bundle, files)
    entries = (script.parent / "connection-files.iss").read_text(encoding="utf-8-sig")
    assert "recursesubdirs createallsubdirs" in entries
