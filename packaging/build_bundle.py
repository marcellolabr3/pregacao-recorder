"""Monta o pacote Windows sem copiar ambientes ou dados pessoais."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PYTHON_VERSION = "3.11.9"
PYTHON_ZIP = "python-3.11.9-embed-amd64.zip"
PYTHON_URL = "https://www.python.org/ftp/python/3.11.9/" + PYTHON_ZIP
PYTHON_SHA256 = "009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b"
RECORDER_FILES = ("config/default.json", ".env.example", "iniciar-tudo.bat", "scripts/pregacao.cmd")
PIPELINE_FILES = ("pipeline.py", "prompt.txt", "config.example.json", "package.json", "package-lock.json", "whatsapp/send.js", "README.md", "SOURCE.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_file(source: Path, target: Path) -> None:
    if source.is_symlink():
        raise ValueError("Nao copiar links simbolicos: " + source.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_sources(source: Path, target: Path) -> None:
    """Allowlist: nunca copiar a arvore inteira nem configuracoes locais."""
    for file in sorted((source / "app").rglob("*.py")):
        if "__pycache__" not in file.parts:
            copy_file(file, target / "gravador" / file.relative_to(source))
    for file in sorted((source / "web").rglob("*")):
        if file.is_file() and file.suffix.lower() in {".html", ".css", ".js", ".json", ".png", ".svg", ".ico", ".woff", ".woff2"}:
            copy_file(file, target / "gravador" / file.relative_to(source))
    for relative in RECORDER_FILES:
        copy_file(source / relative, target / "gravador" / relative)
    for relative in PIPELINE_FILES:
        file = source / "vendor/sermon-pipeline" / relative
        if file.exists():
            copy_file(file, target / "pipeline" / relative)
        elif relative != "README.md":
            raise FileNotFoundError("Fonte necessaria ausente: " + relative)


def extract_runtime(archive: Path, target: Path) -> None:
    if sha256(archive) != PYTHON_SHA256:
        raise ValueError("SHA256 do Python oficial nao corresponde ao runtime fixado")
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for info in package.infolist():
            if not (target / info.filename).resolve().is_relative_to(target.resolve()):
                raise ValueError("Caminho invalido no ZIP do runtime")
        package.extractall(target)
    # _pth is relative to python.exe; no installed Python or developer paths.
    (target / "python311._pth").write_text("python311.zip\n.\nLib/site-packages\n../../gravador\n../../pipeline\nimport site\n", encoding="utf-8")


def public_build_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PIP_", "PREGACAO_", "NOTEBOOKLM_", "PLAYWRIGHT_", "NPM_CONFIG_")) and k not in {"NODE_PATH", "NODE_OPTIONS", "PYTHONPATH", "PYTHONHOME"}}
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_INDEX_URL"] = "https://pypi.org/simple"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run(command: list[str], log: Path, *, cwd: Path | None = None, env: dict | None = None) -> None:
    with log.open("a", encoding="utf-8") as output:
        output.write("\nSTEP " + Path(command[0]).name + " " + command[1] + "\n")
        output.flush()
        result = subprocess.run(command, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError("Etapa falhou (codigo %d); detalhes no log local: %s" % (result.returncode, log))


def find_tool(name: str, explicit: str | None) -> Path:
    file = Path(explicit or shutil.which(name) or "")
    if not file.is_file():
        raise FileNotFoundError("Ferramenta de build nao encontrada: " + name)
    return file.resolve()


def revision(source: Path) -> str:
    result = subprocess.run(["git", "describe", "--always", "--dirty"], cwd=source, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "source-snapshot"


def write_entrypoints(target: Path) -> None:
    for name, suffix in (("Iniciar Pregacao.cmd", ""), ("Verificar Pacote.cmd", " --verificar")):
        content = '@echo off\r\nsetlocal\r\nset "PREGACAO_PACKAGE=%~dp0"\r\npushd "%PREGACAO_PACKAGE%gravador"\r\n"%PREGACAO_PACKAGE%runtime\\python\\python.exe" -B -m app.launcher' + suffix + ' %*\r\nset "PREGACAO_EXIT=%errorlevel%"\r\npopd\r\nif not "%PREGACAO_EXIT%"=="0" pause\r\nexit /b %PREGACAO_EXIT%\r\n'
        (target / name).write_bytes(content.encode("utf-8"))
    (target / "Conectar WhatsApp.cmd").write_bytes((
        '@echo off\r\nsetlocal\r\nset "PREGACAO_PACKAGE=%~dp0"\r\n'
        'set "PREGACAO_PIPELINE_HOME=%PREGACAO_PACKAGE%pipeline"\r\n'
        'set "NODE_PATH="\r\nset "NODE_OPTIONS="\r\n'
        'pushd "%PREGACAO_PACKAGE%pipeline"\r\n'
        '"%PREGACAO_PACKAGE%runtime\\node\\node.exe" "whatsapp\\send.js" --login\r\n'
        'set "PREGACAO_EXIT=%errorlevel%"\r\npopd\r\n'
        'if not "%PREGACAO_EXIT%"=="0" pause\r\nexit /b %PREGACAO_EXIT%\r\n').encode("utf-8"))
    (target / "LEIA-ME.txt").write_text(
        "Pregacao Recorder - pacote pessoal Windows\n\n"
        "Use o instalador .exe para instalar em LOCALAPPDATA/PregacaoRecorder.\n"
        "O ZIP tambem pode ser extraido em uma pasta definitiva gravavel.\n"
        "Execute Verificar Pacote.cmd para diagnostico local sem iniciar servicos.\n"
        "Iniciar Pregacao.cmd abre o programa. Configure audio, pasta e contas em CONFIG.\n"
        "Conectar WhatsApp.cmd permite parear a conta sem enviar mensagens.\n"
        "Leia GUIA-INSTALACAO.md para configuracao, celular e reinstalacao.\n"
        "Este pacote nao contem suas contas, sessoes ou historico.\n"
        "Gravacao local nao exige internet; integracoes precisam de login e conexao.\n"
        "Antes de reinstalar, conclua as tarefas e feche os processos do programa.\n",
        encoding="utf-8")


def copy_browsers(cache: Path, runtime: Path, target: Path, log: Path, env: dict) -> None:
    metadata = json.loads((runtime / "Lib/site-packages/playwright/driver/package/browsers.json").read_text(encoding="utf-8"))
    needed = [b for b in metadata["browsers"] if b["name"] in {"chromium", "chromium-headless-shell", "ffmpeg", "winldd"}]
    available = []
    for browser in needed:
        rev = browser.get("revisionOverrides", {}).get("win64", browser["revision"])
        folder = cache / (browser["name"].replace("-", "_") + "-" + rev)
        if folder.is_dir():
            available.append(folder)
    if len(available) == len(needed):
        target.mkdir(parents=True, exist_ok=True)
        for folder in available:
            shutil.copytree(folder, target / folder.name)
    else:
        browser_env = dict(env, PLAYWRIGHT_BROWSERS_PATH=str(target))
        run([str(runtime / "python.exe"), "-m", "playwright", "install", "chromium"], log, env=browser_env)


def archive_bundle(target: Path) -> Path:
    """Raiz curta evita MAX_PATH ao extrair em Downloads/pastas com espacos."""
    archive = target.with_suffix(".zip")
    temporary = target.with_suffix(".zip.partial")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for file in sorted(target.rglob("*")):
            if file.is_file():
                output.write(file, "PregacaoRecorder/" + file.relative_to(target).as_posix())
    temporary.replace(archive)
    archive.with_suffix(".sha256").write_text(sha256(archive) + "  " + archive.name + "\n", encoding="utf-8")
    return archive


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist-pacote")
    parser.add_argument("--cache", type=Path, default=ROOT / ".bundle-cache")
    parser.add_argument("--browser-cache", type=Path)
    parser.add_argument("--node")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    parser.add_argument("--skip-zip", action="store_true")
    options = parser.parse_args(argv)
    if os.name != "nt" or sys.maxsize <= 2**32:
        parser.error("Build requer Windows x64 com Python 3.11")
    if sys.version_info[:2] != (3, 11):
        parser.error("Usar Python 3.11 para resolver wheels compativeis")
    cache, output = options.cache.resolve(), options.output.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = output / ("PregacaoRecorder-sprint2-" + stamp)
    target.mkdir()
    log = output / ("build-" + stamp + ".log")
    env = public_build_env()
    print("1/7 Fontes por allowlist", flush=True)
    copy_sources(ROOT, target)
    archive = cache / PYTHON_ZIP
    if not archive.exists():
        urllib.request.urlretrieve(PYTHON_URL, archive)
    python = target / "runtime/python"
    extract_runtime(archive, python)
    wheels = cache / "wheels"
    wheels.mkdir(exist_ok=True)
    lock = ROOT / "packaging/requirements-runtime.lock"
    if not lock.is_file():
        raise FileNotFoundError("Gerar requirements-runtime.lock antes de montar o pacote")
    print("2/7 Dependencias Python fixadas", flush=True)
    run([sys.executable, "-m", "pip", "download", "--disable-pip-version-check", "--only-binary=:all:", "--require-hashes", "--dest", str(wheels), "-r", str(lock)], log, env=env)
    site_packages = python / "Lib/site-packages"
    run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-index", "--find-links", str(wheels), "--only-binary=:all:", "--require-hashes", "--no-compile", "--target", str(site_packages), "-r", str(lock)], log, env=env)
    # pip-generated entrypoint launchers contain build-machine interpreter paths.
    # The product invokes modules, so these launchers must not be distributed.
    for folder in (site_packages / "bin", site_packages / "Scripts"):
        if folder.is_dir() and folder.resolve().is_relative_to(target.resolve()):
            shutil.rmtree(folder)
    node = find_tool("node", options.node)
    ffmpeg, ffprobe = find_tool("ffmpeg", options.ffmpeg), find_tool("ffprobe", options.ffprobe)
    copy_file(node, target / "runtime/node/node.exe")
    copy_file(ffmpeg, target / "runtime/ffmpeg/bin/ffmpeg.exe")
    copy_file(ffprobe, target / "runtime/ffmpeg/bin/ffprobe.exe")
    npm = find_tool("npm.cmd", None)
    empty_config = cache / "empty.npmrc"
    empty_config.touch(exist_ok=True)
    npm_env = dict(env, NPM_CONFIG_USERCONFIG=str(empty_config), NPM_CONFIG_REGISTRY="https://registry.npmjs.org")
    print("3/7 Dependencias WhatsApp do lockfile", flush=True)
    run([str(npm), "ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"], log, cwd=target / "pipeline", env=npm_env)
    print("4/7 Navegador de runtime sem perfis", flush=True)
    browser_cache = options.browser_cache or (cache / "browsers")
    copy_browsers(browser_cache, python, target / "runtime/browsers", log, env)
    write_entrypoints(target)
    copy_file(ROOT / "docs/GUIA_INSTALACAO_WINDOWS.md", target / "GUIA-INSTALACAO.md")
    copy_file(ROOT / "docs/ACEITE_WINDOWS.md", target / "ACEITE_WINDOWS.md")
    licenses = target / "licenses"
    licenses.mkdir()
    (licenses / "RUNTIME-SOURCES.txt").write_text("CPython: " + PYTHON_URL + "\nNode: https://nodejs.org/ (binary supplied at build, hash in manifest)\nFFmpeg: https://github.com/yt-dlp/FFmpeg-Builds (binary supplied at build, hash in manifest)\nPython/Node dependencies retain their distribution metadata/licenses.\n", encoding="utf-8")
    with (licenses / "FFmpeg.txt").open("w", encoding="utf-8") as stream:
        subprocess.run([str(ffmpeg), "-L"], stdout=stream, stderr=subprocess.STDOUT)
    manifest = {"schema_version": 1, "name": "PregacaoRecorder", "version": "sprint2-" + stamp, "source_revision": revision(ROOT), "created_at": stamp,
                "layout": {"recorder": "gravador", "pipeline": "pipeline", "python": "runtime/python", "node": "runtime/node/node.exe", "ffmpeg": "runtime/ffmpeg/bin", "browsers": "runtime/browsers"},
                "components": {"python": {"version": PYTHON_VERSION, "archive_sha256": PYTHON_SHA256}, "node": {"version": subprocess.check_output([str(node), "--version"], text=True).strip(), "sha256": sha256(node)}, "ffmpeg": {"sha256": sha256(ffmpeg)}, "ffprobe": {"sha256": sha256(ffprobe)}, "python_lock_sha256": sha256(lock)}}
    (target / "package-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("5/7 Smoke isolado sem contas, rede ou captura", flush=True)
    run([str(python / "python.exe"), "-B", str(ROOT / "packaging/smoke_bundle.py"), str(target)], log, env=env)
    print("6/7 Hashes e inventario final", flush=True)
    manifest["files"] = {file.relative_to(target).as_posix(): sha256(file) for file in sorted(target.rglob("*")) if file.is_file() and file.name != "package-manifest.json"}
    (target / "package-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if not options.skip_zip:
        print("7/7 Compactando pacote", flush=True)
        path = archive_bundle(target)
        print("ZIP:", path, flush=True)
    print("PACOTE:", target, flush=True)
    print("LOG:", log, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
