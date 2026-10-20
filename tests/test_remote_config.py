"""Configuracao MQTT pela tela existente, sem broker nem dados pessoais."""
from __future__ import annotations

from contextlib import nullcontext
import json
from types import SimpleNamespace

import pytest

from app.remote.agent import RemoteSettings, topics
from app.remote.settings import ENV_KEYS, effective_environment, validate_update
from app.states import State


@pytest.fixture
def remote_client(monkeypatch, cfg, fresh_state):
    from flask import Flask
    from app.api import routes

    for name in ENV_KEYS.values():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PREGACAO_PIN", "1234")
    monkeypatch.setenv("PREGACAO_ADMIN_PIN", "5678")
    monkeypatch.setattr(routes, "_remote_restart_required", False)
    monkeypatch.setattr(routes, "_agente_visto_em", 0.0)
    monkeypatch.setattr(routes.estudos, "iniciar", lambda: None)
    monkeypatch.setattr(routes.estudos, "status", lambda: {"login": {"em_andamento": False}})
    monkeypatch.setattr(routes.db, "job_contagens", lambda: {})
    monkeypatch.setattr(routes.db, "list_jobs", lambda *_: [])
    monkeypatch.setattr(routes.drive, "status", lambda: {})
    monkeypatch.setattr(routes.audio_device, "list_devices", lambda: [])
    monkeypatch.setattr(routes.audio_device, "detect", lambda *_: None)
    notifications = []
    monkeypatch.setattr(routes.notify, "notify", lambda *args, **kwargs: notifications.append((args, kwargs)))
    uploader = SimpleNamespace(snapshot=lambda: {"running": 0})
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="segredo-sintetico")
    routes.register_routes(app, SimpleNamespace(), uploader)
    with app.test_client() as client:
        yield SimpleNamespace(client=client, uploader=uploader, routes=routes, notifications=notifications)


def _admin(client):
    with client.session_transaction() as session:
        session.update(auth=True, admin=True)


def _settings(**updates):
    result = {
        "enabled": True, "host": "broker.invalid", "port": 8883, "tls": True,
        "username": "pc-sintetico", "password": "senha-pc-sintetica",
        "device_id": "pregacao-pc-novo", "operator_token": "token-operador-sintetico",
    }
    result.update(updates)
    return result


def test_remote_save_requires_authenticated_administrator(remote_client, cfg):
    client = remote_client.client
    assert client.post("/api/remote/config", json=_settings()).status_code == 401
    with client.session_transaction() as session:
        session["auth"] = True
    assert client.post("/api/remote/config", json=_settings()).status_code == 403
    assert cfg.get("remote") is None


def test_mqtt_persists_and_reloads_with_one_identity_without_exposing_pc_password(remote_client, cfg, monkeypatch):
    client = remote_client.client
    _admin(client)
    cfg.set("device_name", "Nome anterior preservado")
    monkeypatch.setenv("PREGACAO_REMOTE_HOST", "broker-anterior.invalid")
    monkeypatch.setenv("PREGACAO_DEVICE_ID", "id-legado")
    response = client.post("/api/remote/config", json=_settings())
    assert response.status_code == 200
    result = response.get_json()
    assert result["restart_required"] is True
    assert "reinicie o Windows" in result["message"]
    assert result["remote"]["service"] == "restart_required"
    assert result["remote"]["topics"] == topics("pregacao-pc-novo")
    assert "senha-pc-sintetica" not in response.get_data(as_text=True)
    cfg.reload()
    assert cfg.get("remote.password") == "senha-pc-sintetica"
    assert cfg.get("device_name") == "Nome anterior preservado"
    assert cfg.device_id == RemoteSettings().device_id == "pregacao-pc-novo"
    assert RemoteSettings().host == "broker.invalid"
    assert RemoteSettings().password == "senha-pc-sintetica"
    view = client.get("/api/config").get_json()
    assert "remote" not in view["config"]
    assert view["remote"]["password_configured"] is True
    assert view["remote"]["username"] == "pc-sintetico"
    assert view["remote"]["operator_token_configured"] is True
    assert "senha-pc-sintetica" not in str(view)
    assert "senha-pc-sintetica" not in str(remote_client.notifications)
    assert "token-operador-sintetico" not in str(remote_client.notifications)
    # Um ambiente sintetico explicito nao deve importar preferencias de outro teste/PC.
    assert RemoteSettings(environ={"PREGACAO_REMOTE_HOST": "isolado.invalid"}).host == "isolado.invalid"


def test_blank_secret_fields_preserve_legacy_credentials_without_touching_env_file(remote_client, cfg, monkeypatch, home):
    monkeypatch.setenv("PREGACAO_REMOTE_PASSWORD", "senha-legada")
    monkeypatch.setenv("PREGACAO_OPERATOR_TOKEN", "token-legado")
    env_path = home / ".env"
    original = env_path.read_bytes() if env_path.exists() else None
    _admin(remote_client.client)
    result = remote_client.client.post("/api/remote/config", json=_settings(password="", operator_token=""))
    assert result.status_code == 200
    assert cfg.get("remote.password") == "senha-legada"
    assert cfg.get("remote.operator_token") == "token-legado"
    assert (env_path.read_bytes() if env_path.exists() else None) == original


@pytest.mark.parametrize("updates", [
    {"host": "mqtts://broker.invalid"}, {"host": "broker.invalid:8883"},
    {"host": "broker.invalid/topic"}, {"host": "broker invalid"}, {"host": "+.invalid"},
    {"host": ""}, {"port": 0}, {"port": 65536}, {"port": True}, {"port": "8883"},
    {"tls": "false"}, {"enabled": "false"}, {"device_id": "novo/+"},
    {"device_id": "novo/#"}, {"device_id": "novo/pc"}, {"device_id": ""},
    {"device_id": "x" * 33}, {"device_id": "_novo"}, {"username": "usuario\nnovo"},
    {"password": "senha\rnova"}, {"operator_token": "token\x00novo"}, {"topics": "outro/#"},
])
def test_invalid_remote_changes_are_rejected_atomically(remote_client, cfg, updates):
    cfg.set("remote", _settings())
    cfg.save()
    before = cfg.user_file.read_bytes()
    _admin(remote_client.client)
    response = remote_client.client.post("/api/remote/config", json=_settings(**updates))
    assert response.status_code == 422
    assert cfg.get("remote") == _settings()
    assert cfg.user_file.read_bytes() == before
    assert remote_client.routes._remote_restart_required is False


@pytest.mark.parametrize("body", [None, [], "texto", {}])
def test_remote_rejects_wrong_json_shape(remote_client, body):
    _admin(remote_client.client)
    assert remote_client.client.post("/api/remote/config", json=body).status_code == 422


@pytest.mark.parametrize("state", [State.RECORDING, State.FINALIZING, State.UPLOADING])
def test_remote_does_not_change_during_recording_or_finalization(remote_client, fresh_state, cfg, state):
    fresh_state.set(state, force=True)
    _admin(remote_client.client)
    assert remote_client.client.post("/api/remote/config", json=_settings()).status_code == 409
    assert cfg.get("remote") is None


@pytest.mark.parametrize("activity", ["upload", "study", "login"])
def test_remote_does_not_change_during_background_activity(remote_client, cfg, monkeypatch, activity):
    if activity == "upload":
        remote_client.uploader.snapshot = lambda: {"running": 1}
    elif activity == "study":
        monkeypatch.setattr(remote_client.routes.db, "job_contagens", lambda: {"EXECUTANDO": 1})
    else:
        monkeypatch.setattr(remote_client.routes.estudos, "status", lambda: {"login": {"em_andamento": True}})
    _admin(remote_client.client)
    assert remote_client.client.post("/api/remote/config", json=_settings()).status_code == 409
    assert cfg.get("remote") is None


def test_failure_to_save_does_not_change_memory_or_existing_file(remote_client, cfg, monkeypatch):
    cfg.set("remote", _settings())
    cfg.save()
    before = cfg.user_file.read_bytes()
    monkeypatch.setattr(cfg, "save", lambda: (_ for _ in ()).throw(OSError("falha sintetica")))
    _admin(remote_client.client)
    result = remote_client.client.post("/api/remote/config", json=_settings(host="outro.invalid"))
    assert result.status_code == 500
    assert cfg.get("remote") == _settings()
    assert cfg.user_file.read_bytes() == before
    assert remote_client.routes._remote_restart_required is False


def test_old_agent_heartbeat_does_not_claim_new_config_is_connected(remote_client, monkeypatch):
    import time

    _admin(remote_client.client)
    assert remote_client.client.post("/api/remote/config", json=_settings()).status_code == 200
    monkeypatch.setattr(remote_client.routes, "_agente_visto_em", time.time())
    state = remote_client.client.get("/api/integracoes").get_json()["emqx"]
    assert state["estado"] == "verificando"
    assert "reinicio pendente" in state["detalhe"]


@pytest.mark.parametrize("host", ["localhost", "192.0.2.1", "2001:db8::1", "mqtt.example.invalid"])
def test_valid_hosts_and_custom_tls_port_are_accepted(host):
    current = RemoteSettings(environ={})
    result = validate_update(_settings(host=host, port=1884, tls=True), current)
    assert result["host"] == host
    assert result["tls"] is True


def test_disabled_unconfigured_installation_can_be_saved():
    current = RemoteSettings(environ={})
    result = validate_update(_settings(enabled=False, host=""), current)
    assert result["enabled"] is False
    assert result["host"] == ""


def test_partial_update_does_not_preserve_invalid_legacy_port():
    current = RemoteSettings(environ={"PREGACAO_REMOTE_PORT": "99999"})
    with pytest.raises(ValueError, match="porta MQTT"):
        validate_update({"enabled": False}, current)


@pytest.mark.parametrize("mode", ["start", "diagnostic"])
def test_launcher_and_diagnostic_use_saved_config_instead_of_old_environment(tmp_path, monkeypatch, mode):
    from app import bundled_runtime, launcher

    home = tmp_path / "Instalacao com espacos e acentos"
    (home / "config").mkdir(parents=True)
    (home / "config" / "config.json").write_text(json.dumps({"remote": _settings()}), encoding="utf-8")
    monkeypatch.setenv("PREGACAO_HOME", str(home))
    monkeypatch.setenv("PREGACAO_REMOTE_HOST", "")
    monkeypatch.setenv("PREGACAO_REMOTE_ENABLED", "0")
    monkeypatch.setattr(bundled_runtime, "prepare_environment", lambda **_: None)
    monkeypatch.setattr(launcher, "_launch_lock", lambda *_: nullcontext())
    monkeypatch.setattr(launcher, "_file_logger", lambda *_: SimpleNamespace(info=lambda *_: None, warning=lambda *_: None))
    calls = []
    monkeypatch.setattr(launcher, "launch", lambda component, root, data_home, env, url: calls.append((component, dict(env))) or True)
    monkeypatch.setattr(launcher, "diagnostic", lambda cfg, env: calls.append(("diagnostic", dict(env))) or 0)
    before = sorted(home.rglob("*"))
    assert launcher.main(["--verificar"] if mode == "diagnostic" else ["--sem-navegador"]) == 0
    assert [call[0] for call in calls] == (["diagnostic"] if mode == "diagnostic" else ["gravador", "agente"])
    assert sorted(home.rglob("*")) == before
    for _, env in calls:
        assert env["PREGACAO_REMOTE_HOST"] == "broker.invalid"
        assert env["PREGACAO_REMOTE_ENABLED"] == "1"
        assert env["PREGACAO_DEVICE_ID"] == "pregacao-pc-novo"
    assert effective_environment(SimpleNamespace(get=lambda *_: {}), {"LEGADO": "preservado"}) == {"LEGADO": "preservado"}
