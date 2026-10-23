"""Builds must leave their generated files inside the checkout."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "packaging" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(os.name != "nt", reason="O build final requer Windows")
def test_release_build_stages_and_tool_caches_inside_checkout(tmp_path, monkeypatch):
    assert tmp_path.is_relative_to(ROOT / ".w")
    builder = load("build_release_paths", "build_release.py")
    project = tmp_path / "checkout"
    flutter_project = project / "flutter" / "pregacao_controle"
    flutter_project.mkdir(parents=True)
    (flutter_project / "pubspec.yaml").write_text("version: 2.9.0+15\n")
    signing = project / ".signing" / "debug.keystore"
    signing.parent.mkdir()
    signing.write_bytes(b"fixture-key")
    flutter = project / "tools" / "flutter.bat"
    flutter.parent.mkdir()
    flutter.write_bytes(b"fixture")
    compiler = project / "tools" / "ISCC.exe"
    compiler.write_bytes(b"fixture")
    cache = project / ".bundle-cache"
    work_root = project / ".w"
    for name, value in (("ROOT", project), ("FLUTTER_PROJECT", flutter_project),
                        ("BUILD_CACHE", cache), ("WORK_ROOT", work_root),
                        ("SIGNING_KEY", signing)):
        monkeypatch.setattr(builder, name, value)

    calls = []

    def checked(command, *, cwd=project, env=None):
        calls.append((command, env))
        assert env is not None
        for name in ("TEMP", "TMP", "TMPDIR", "PUB_CACHE", "GRADLE_USER_HOME",
                     "ANDROID_USER_HOME", "NPM_CONFIG_CACHE"):
            assert Path(env[name]).resolve().is_relative_to(project), name
        assert "ANDROID_PREFS_ROOT" not in env
        if command[1:3] == ["build", "apk"]:
            apk = flutter_project / "build/app/outputs/flutter-apk/app-release.apk"
            apk.parent.mkdir(parents=True)
            apk.write_bytes(b"apk")
        elif Path(command[2]).name == "build_bundle.py":
            output = Path(command[command.index("--output") + 1])
            (output / "PregacaoRecorder-release-fixture").mkdir(parents=True)
        elif Path(command[2]).name == "build_installer.py":
            output = Path(command[command.index("--output") + 1])
            output.mkdir(parents=True)
            (output / "Gerador de Estudo.exe").write_bytes(b"installer")

    monkeypatch.setattr(builder, "checked", checked)
    assert builder.main(["--flutter", str(flutter), "--iscc", str(compiler)]) == 0
    assert len(calls) == 4
    assert (project / "dist-pacote" / "Gerador de Estudo.exe").read_bytes() == b"installer"
    assert (project / "dist-pacote" / "Controle Android.apk").read_bytes() == b"apk"
    assert not list(work_root.glob("b-*"))


def test_bundle_subprocess_cache_and_temp_stay_inside_checkout(tmp_path):
    assert tmp_path.is_relative_to(ROOT / ".w")
    builder = load("build_bundle_paths", "build_bundle.py")
    cache = tmp_path / ".bundle-cache"
    env = builder.public_build_env(cache)
    assert env["PIP_NO_CACHE_DIR"] == "1"
    assert Path(env["TEMP"]) == cache / "tmp"
    assert Path(env["TMP"]) == cache / "tmp"
    assert Path(env["NPM_CONFIG_CACHE"]) == cache / "npm"
