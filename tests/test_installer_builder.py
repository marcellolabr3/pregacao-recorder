"""Inventario do instalador: hash/allowlist impedem copiar dados locais por engano."""
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("installer_builder", ROOT / "packaging/build_installer.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "pacote com acentos & espacos"
    files = {}
    for relative in ["Iniciar Pregacao.cmd", "Verificar Pacote.cmd", "gravador/app/launcher.py",
                     "gravador/config/default.json", "runtime/python/python.exe"]:
        file = root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"public-fixture")
        files[relative] = hashlib.sha256(file.read_bytes()).hexdigest()
    manifest = {"name": "PregacaoRecorder", "schema_version": 1, "version": "sprint2-test", "files": files}
    (root / "package-manifest.json").write_text(json.dumps(manifest))
    return root


def test_installer_copies_only_inventory_not_unlisted_private_files(bundle, tmp_path):
    private = bundle / "gravador/.env"
    private.write_text("fixture-private")
    script, name = installer.prepare_script(bundle, tmp_path / "build", tmp_path / "output")
    entries = (script.parent / "bundle-files.iss").read_text(encoding="utf-8-sig")
    assert str(private) not in entries
    assert "recursesubdirs" not in entries
    assert "gravador/app/launcher.py" in entries.replace("\\", "/")
    assert name == "PregacaoRecorder-Instalar-sprint2-test"


def test_tampered_payload_rejected_before_compilation(bundle):
    (bundle / "gravador/app/launcher.py").write_text("changed")
    with pytest.raises(ValueError, match="alterado"):
        installer.validated_files(bundle)


@pytest.mark.parametrize("relative", ["../outside", "C:/private", "gravador/.env", "gravador/config/config.json",
    "gravador/config/google_token.json", "gravador/data/pregacao.db", "gravador/recordings/test.mp3",
    "pipeline/config.json", "pipeline/whatsapp/auth/creds.json", "pipeline/whatsapp/qr.png",
    "gravador/app/../../.env", "runtime/../private", "runtime/file\nother", "runtime/file\\other",
    "gravador/web/profile.sqlite", "runtime/profile/.env", "runtime/python/profile/google_token.json",
    "pipeline/node_modules/example/.env", "runtime/browsers/qr_12345.png"])
def test_invalid_or_mutable_inventory_rejected(relative, bundle):
    marker = bundle / "package-manifest.json"
    data = json.loads(marker.read_text())
    data["files"][relative] = "0" * 64
    marker.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="privado ou invalido"):
        installer.validated_files(bundle)


def test_smoke_installer_cannot_write_registry_or_desktop(bundle, tmp_path):
    script, name = installer.prepare_script(bundle, tmp_path / "build", tmp_path / "output", smoke=True)
    text = script.read_text(encoding="utf-8-sig")
    assert "#define SmokeTestBuild" in text
    assert name.endswith("-smoke")


def test_unversioned_or_incomplete_package_rejected(bundle):
    marker = bundle / "package-manifest.json"
    data = json.loads(marker.read_text())
    del data["files"]["runtime/python/python.exe"]
    marker.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="incompleto"):
        installer.validated_files(bundle)


def test_personal_update_checks_hash_before_replacing_public_files(bundle, tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "packaging"))
    update = importlib.import_module("build_personal_update")
    apk = tmp_path / "PregacaoControle-2.7.apk"
    apk.write_bytes(b"apk-fixture")
    (bundle / "gravador/.env").write_text("private-fixture")

    script, _ = update.prepare_update(bundle, apk, tmp_path / "output")
    entries = (script.parent / "update-files.iss").read_text(encoding="utf-8-sig")
    manifest = script.parent / "package-manifest.json"
    public_hash = hashlib.sha256((bundle / "gravador/app/launcher.py").read_bytes()).hexdigest()
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    apk_hash = hashlib.sha256(apk.read_bytes()).hexdigest()

    assert f"NeedsUpdate('gravador\\app\\launcher.py', '{public_hash}')" in entries
    assert f"NeedsUpdate('package-manifest.json', '{manifest_hash}')" in entries
    assert f"NeedsUpdate('PregacaoControle-2.7.apk', '{apk_hash}')" in entries
    assert "gravador/.env" not in entries
