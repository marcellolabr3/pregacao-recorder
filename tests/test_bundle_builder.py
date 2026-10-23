"""Empacotamento por allowlist: fontes sim, dados/credenciais locais nao."""
from pathlib import Path
import importlib.util
import json
import re
import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('pregacao_bundle_builder', ROOT / 'packaging/build_bundle.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_copy_sources_does_not_include_local_data(tmp_path):
    source, target = tmp_path / 'source', tmp_path / 'bundle'
    required = ['app/main.py', 'web/templates/index.html', *builder.RECORDER_FILES]
    for name in builder.PIPELINE_FILES:
        required.append('vendor/sermon-pipeline/' + name)
    private = ['.env', 'config/config.json', 'config/google_token.json', 'docs/CODEX_CONTEXT.local.md', 'data/pregacao.db', 'recordings/culto.mp3', 'logs/service.log', '.venv/pyvenv.cfg', 'app/__pycache__/main.pyc', 'vendor/sermon-pipeline/config.json', 'vendor/sermon-pipeline/whatsapp/auth/creds.json', 'vendor/sermon-pipeline/whatsapp/qr.png', 'vendor/sermon-pipeline/.npmrc', 'vendor/sermon-pipeline/node_modules/private.txt']
    for relative in required + private:
        file = source / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('fixture-public' if relative in required else 'fixture-private', encoding='utf-8')
    builder.copy_sources(source, target)
    assert (target / 'gravador/app/main.py').is_file()
    assert (target / 'pipeline/prompt.txt').is_file()
    for file in target.rglob('*'):
        if file.is_file():
            assert file.read_text() == 'fixture-public', file.relative_to(target)


def test_copy_sources_requires_pipeline(tmp_path):
    source = tmp_path / 'source'
    for relative in builder.RECORDER_FILES:
        file = source / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('fixture')
    with pytest.raises(FileNotFoundError):
        builder.copy_sources(source, tmp_path / 'bundle')


def test_runtime_archive_is_pinned_and_rejects_tampering(tmp_path):
    archive = tmp_path / 'runtime.zip'
    archive.write_bytes(b'not the official archive')
    with pytest.raises(ValueError, match='SHA256'):
        builder.extract_runtime(archive, tmp_path / 'python')
    assert not (tmp_path / 'python').exists()


@pytest.mark.parametrize("shell_cached", [False, True])
def test_browser_cache_reused_only_when_login_and_recovery_browsers_present(tmp_path, monkeypatch, shell_cached):
    runtime, cache, target = (tmp_path / name for name in ("python", "cache", "browsers"))
    metadata = runtime / "Lib/site-packages/playwright/driver/package/browsers.json"
    metadata.parent.mkdir(parents=True)
    browsers = [
        {"name": "chromium", "revision": "100"},
        {"name": "chromium-headless-shell", "revision": "100"},
        {"name": "ffmpeg", "revision": "200"},
        {"name": "winldd", "revision": "300"},
    ]
    metadata.write_text(json.dumps({"browsers": browsers}))
    for browser in browsers:
        if browser["name"] == "chromium-headless-shell" and not shell_cached:
            continue
        folder = cache / (browser["name"].replace("-", "_") + "-" + browser["revision"])
        folder.mkdir(parents=True)
        (folder / "fixture.txt").write_text(browser["name"])
    calls = []
    monkeypatch.setattr(builder, "run", lambda command, log, **kwargs: calls.append((command, kwargs["env"])))
    builder.copy_browsers(cache, runtime, target, tmp_path / "build.log", {"FIXTURE": "1"})
    if shell_cached:
        assert calls == []
        assert sorted(file.read_text() for file in target.rglob("fixture.txt")) == sorted(b["name"] for b in browsers)
    else:
        # A cache adequate for interactive login still needs the recovery
        # browser; provision both through the private runtime, without --no-shell.
        assert calls == [([str(runtime / "python.exe"), "-m", "playwright", "install", "chromium"],
                          {"FIXTURE": "1", "PLAYWRIGHT_BROWSERS_PATH": str(target)})]


def test_runtime_lock_contains_exact_hashes_and_correct_notebooklm():
    text = (ROOT / 'packaging/requirements-runtime.lock').read_text()
    lines = [line for line in text.splitlines() if line and not line.startswith('#')]
    assert lines
    assert all(re.fullmatch(r'[A-Za-z0-9_.-]+==[^ ]+ --hash=sha256:[a-f0-9]{64}', line) for line in lines)
    assert 'notebooklm-py==0.8.5 ' in text
    assert 'notebooklm-py[headless]==0.8.5' in (ROOT / 'packaging/requirements-runtime.in').read_text()
    assert 'gpsoauth==2.0.0 ' in text
    assert 'pycryptodomex==3.24.1 ' in text
    assert '\nnotebooklm==' not in text
    assert 'openpyxl==3.1.5 ' in text
    # Installed NotebookLM uses its dedicated browser profile. Do not ship
    # the optional native reader for cookies from unrelated browsers.
    assert 'rookie-cookies' not in text
    assert 'rookie-cookies' not in (ROOT / 'packaging/requirements-runtime.in').read_text()


def test_entrypoints_use_relative_private_runtime(tmp_path):
    builder.write_entrypoints(tmp_path)
    startup = (tmp_path / 'Iniciar Pregacao.cmd').read_text()
    assert '%PREGACAO_PACKAGE%runtime\\python\\python.exe' in startup
    assert startup.index('set \"PREGACAO_PACKAGE=%~dp0\"') < startup.index('pushd')
    assert '-m app.launcher' in startup
    assert r'D:\Dev' not in startup
    assert '--verificar' in (tmp_path / 'Verificar Pacote.cmd').read_text()


def test_archive_uses_short_root_and_contains_matching_checksum(tmp_path):
    import hashlib
    import zipfile
    stage = tmp_path / "PregacaoRecorder-sprint1-long-version-timestamp"
    nested = stage / "runtime/python/Lib/site-packages/dependency/deep/module.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("# test")
    archive = builder.archive_bundle(stage)
    with zipfile.ZipFile(archive) as package:
        assert package.namelist() == ["PregacaoRecorder/runtime/python/Lib/site-packages/dependency/deep/module.py"]
        assert package.read(package.namelist()[0]) == b"# test"
    assert archive.with_suffix('.sha256').read_text().split()[0] == hashlib.sha256(archive.read_bytes()).hexdigest()
