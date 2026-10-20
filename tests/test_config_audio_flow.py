"""CONFIG e teste de sinal com arquivos isolados e captura simulada."""
from pathlib import Path

import pytest

flask = pytest.importorskip("flask")

from app.api import auth, routes
from app.audio import device
from app.config import Config
from app.storage import destinos
from app.upload import drive


DEVICES = [
    {"hw": "Mesa USB", "card_id": "mesa-usb", "name": "Mesa USB", "usb": True},
    {"hw": "Microfone PC", "card_id": "microfone-pc", "name": "Microfone PC", "usb": False},
]


@pytest.fixture()
def setup_client(tmp_path, monkeypatch):
    folder = tmp_path / "config"
    folder.mkdir()
    defaults = Path(__file__).resolve().parents[1] / "config" / "default.json"
    (folder / "default.json").write_text(defaults.read_text(encoding="utf-8"), encoding="utf-8")
    cfg = Config(tmp_path)
    cfg.set("audio.device", "Mesa USB")
    cfg.save()
    monkeypatch.setattr(routes, "config", cfg)
    monkeypatch.setattr(auth, "config", cfg)
    monkeypatch.setattr(drive, "app_config", cfg)
    monkeypatch.setenv("PREGACAO_PIN", "1234")
    monkeypatch.setenv("PREGACAO_ADMIN_PIN", "1234")
    monkeypatch.setattr(device, "list_devices", lambda: DEVICES)
    monkeypatch.setattr(routes.estudos, "iniciar", lambda: None)
    monkeypatch.setattr(routes.notify, "notify", lambda *args, **kwargs: None)
    monkeypatch.setattr(routes, "remote_status", lambda: {})
    monkeypatch.setattr(drive, "status", lambda: {"connected": False})
    monkeypatch.setattr(destinos, "unidades", lambda: [])
    app = flask.Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="config-audio-test")
    routes.register_routes(app, None, None)
    with app.test_client() as client:
        with client.session_transaction() as session:
            session.update(auth=True, admin=True)
        yield client, cfg


def test_invalid_config_preserves_memory_disk_and_destination(setup_client, tmp_path):
    client, cfg = setup_client
    before = cfg.as_dict()
    persisted = cfg.user_file.read_bytes()
    destination = tmp_path / "novo destino"
    response = client.post("/api/config", json={
        "audio.device": "Microfone PC", "audio.sample_rate": 12345,
        "storage.recordings_dir": str(destination),
    })
    assert response.status_code == 422
    assert cfg.as_dict() == before
    assert cfg.user_file.read_bytes() == persisted
    assert not destination.exists()


def test_audio_destination_and_drive_preferences_survive_reopen(setup_client, tmp_path):
    client, cfg = setup_client
    destination = tmp_path / "Audios com acentuação"
    response = client.post("/api/config", json={
        "audio.device": "Microfone PC", "audio.sample_rate": 48000, "audio.channels": 1,
        "storage.recordings_dir": str(destination),
        "drive.client_id": "teste.apps.googleusercontent.com",
        "drive.client_secret": "oauth-test-secret", "drive.folder_name": "Igreja teste",
        "estudos.whatsapp": "+5511999999999",
    })
    assert response.status_code == 200
    reopened = Config(tmp_path)
    assert reopened.get("audio.device") == "Microfone PC"
    assert reopened.get("audio.sample_rate") == 48000
    assert reopened.get("audio.channels") == 1
    assert reopened.recordings_root == destination
    assert reopened.get("drive.client_secret") == "oauth-test-secret"
    assert reopened.get("estudos.whatsapp") == "+5511999999999"
    cfg.reload()
    data = client.get("/api/config").get_json()["config"]
    assert data["audio"]["device"] == "Microfone PC"
    assert data["storage"]["recordings_dir"] == str(destination)
    assert data["drive"]["client_secret"] == ""
    assert data["drive"]["client_secret_set"] is True


def test_existing_unavailable_audio_is_preserved_when_saving_other_preferences(setup_client):
    client, cfg = setup_client
    cfg.update_and_save({"audio.device": "Mesa desconectada"})
    response = client.post("/api/config", json={"audio.device": "Mesa desconectada", "audio.bitrate": 192})
    assert response.status_code == 200
    cfg.reload()
    assert cfg.get("audio.device") == "Mesa desconectada"
    assert cfg.get("audio.bitrate") == 192
    assert client.post("/api/config", json={"audio.device": "Outra inexistente"}).status_code == 422


def test_storage_selection_survives_reopen(setup_client, tmp_path):
    client, cfg = setup_client
    destination = tmp_path / "Outro disco" / "Pregações"
    assert client.post("/api/storage", json={"path": str(destination)}).status_code == 200
    assert destination.is_dir()
    assert Config(tmp_path).recordings_root == destination
    assert client.get("/api/storage").get_json()["current"] == str(destination)
    assert client.post("/api/storage", json={"path": "relativo"}).status_code == 422
    assert cfg.recordings_root == destination


def test_config_failed_write_restores_memory_and_previous_file(setup_client, monkeypatch, tmp_path):
    _, cfg = setup_client
    previous = cfg.as_dict()
    def fail_save():
        raise PermissionError("simulated read-only configuration")
    monkeypatch.setattr(cfg, "save", fail_save)
    with pytest.raises(PermissionError):
        cfg.update_and_save({"audio.device": "Microfone PC", "audio.channels": 1})
    assert cfg.as_dict() == previous
    assert Config(tmp_path).as_dict() == previous


@pytest.mark.parametrize("endpoint, body", [
    ("/api/config", {"audio.device": "Microfone PC"}),
    ("/api/storage", None),
])
def test_config_save_error_is_reported_without_applying_changes(setup_client, monkeypatch, tmp_path, endpoint, body):
    client, cfg = setup_client
    before = cfg.as_dict()
    def fail_save():
        raise PermissionError("simulated read-only configuration")
    monkeypatch.setattr(cfg, "save", fail_save)
    response = client.post(endpoint, json=body or {"path": str(tmp_path / "destino")})
    assert response.status_code == 500
    assert response.get_json()["error"] == "config_save_falhou"
    assert cfg.as_dict() == before
    assert Config(tmp_path).as_dict() == before


def test_audio_test_uses_unsaved_selection_without_persisting(setup_client, monkeypatch):
    client, cfg = setup_client
    before = cfg.user_file.read_bytes()
    calls = []
    def capture(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "silent": False, "peak_db": -12.0}
    monkeypatch.setattr(device, "capture_level", capture)
    response = client.post("/api/audio/test", json={"device": "Microfone PC", "sample_rate": "48000", "channels": "2"})
    assert response.status_code == 200
    assert calls == [{"seconds": 2.0, "device": "Microfone PC", "sample_rate": 48000, "channels": 2}]
    assert response.get_json()["device"]["hw"] == "Microfone PC"
    assert cfg.get("audio.device") == "Mesa USB"
    assert cfg.user_file.read_bytes() == before


def test_audio_test_without_overrides_uses_saved_settings_for_operator(setup_client, monkeypatch):
    client, cfg = setup_client
    cfg.set("audio.sample_rate", 32000)
    cfg.set("audio.channels", 2)
    calls = []
    monkeypatch.setattr(device, "capture_level", lambda **kwargs: calls.append(kwargs) or {"ok": False, "error": "simulado"})
    with client.session_transaction() as session:
        session["admin"] = False
    response = client.post("/api/audio/test")
    assert response.status_code == 200
    assert calls == [{"seconds": 2.0, "device": "Mesa USB", "sample_rate": 32000, "channels": 2}]
    assert client.post("/api/audio/test", json={"device": "Microfone PC"}).status_code == 403
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [
    {"device": "Ausente"}, {"device": ""}, {"device": None},
    {"sample_rate": 12345}, {"sample_rate": 48000.1},
    {"channels": 3}, {"channels": True}, {"channels": "1.5"}, {"seconds": 600},
])
def test_audio_test_rejects_invalid_override_before_capture(setup_client, monkeypatch, payload):
    client, cfg = setup_client
    previous = cfg.as_dict()
    def forbidden(**kwargs):
        pytest.fail("invalid audio selection must not start capture")
    monkeypatch.setattr(device, "capture_level", forbidden)
    assert client.post("/api/audio/test", json=payload).status_code == 422
    assert cfg.as_dict() == previous


def test_audio_test_rejects_non_object_payload(setup_client):
    client, _ = setup_client
    assert client.post("/api/audio/test", json=["Mesa USB"]).status_code == 400
