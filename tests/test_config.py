import json
from pathlib import Path

from app.config import Config


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_defaults_loaded(cfg):
    assert cfg.get("audio.sample_rate") == 44100
    assert cfg.get("audio.channels") == 2
    assert cfg.get("drive.auto_upload") is True


def test_get_supports_dotted_path(cfg):
    assert cfg.get("audio.nao.existe", "padrao") == "padrao"
    assert cfg.get("audio.sample_rate") is not None


def test_set_and_save_persists(home: Path):
    cfg = Config(home)
    cfg.set("device_name", "Igreja Central")
    cfg.set("audio.bitrate", 192)
    cfg.save()

    reloaded = Config(home)
    assert reloaded.get("device_name") == "Igreja Central"
    assert reloaded.get("audio.bitrate") == 192
    # valores default continuam acessiveis
    assert reloaded.get("audio.channels") == 2


def test_set_creates_nested_dicts(cfg, home: Path):
    cfg.set("novo.bloco.chave", 1)
    assert cfg.get("novo.bloco.chave") == 1


def test_user_overrides_default(home: Path):
    _write(home / "config" / "default.json", {"audio": {"sample_rate": 44100, "channels": 2}})
    _write(home / "config" / "config.json", {"audio": {"sample_rate": 48000}})
    cfg = Config(home)
    assert cfg.get("audio.sample_rate") == 48000
    assert cfg.get("audio.channels") == 2


def test_corrupted_user_config_falls_back_to_defaults(home: Path):
    _write(home / "config" / "default.json", {"audio": {"channels": 2}})
    (home / "config" / "config.json").write_text("{quebrado", encoding="utf-8")
    cfg = Config(home)
    assert cfg.get("audio.channels") == 2


def test_recordings_root_fallback(home: Path, cfg):
    cfg.set("storage.recordings_dir", "")
    assert cfg.recordings_root == home / "recordings"
    cfg.set("storage.recordings_dir", str(home / "externo"))
    assert cfg.recordings_root == home / "externo"


def test_port_from_env(cfg, monkeypatch):
    monkeypatch.setenv("PREGACAO_PORT", "9999")
    assert cfg.port == 9999
    monkeypatch.setenv("PREGACAO_PORT", "abc")
    assert cfg.port == 8080
