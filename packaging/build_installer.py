"""Compila o instalador pessoal somente com arquivos publicos inventariados."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def digest(file: Path) -> str:
    value = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def public_path(relative: str) -> bool:
    """Nunca instalar dados mutaveis, mesmo se incluidos num manifesto adulterado."""
    if not isinstance(relative, str) or any(c in relative for c in '\\:"\r\n'):
        return False
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        return False
    if path.name.casefold() in {".env", ".npmrc", "google_token.json", "google_credentials.json",
                                "storage_state.json", "creds.json", "cookies", "cookies.sqlite", "login data", "qr.png"}:
        return False
    if re.fullmatch(r"qr_\d+\.png", path.name, re.IGNORECASE):
        return False
    if relative.startswith("gravador/"):
        local = relative.removeprefix("gravador/")
        return ((local.startswith("app/") and path.suffix == ".py")
                or (local.startswith("web/") and path.suffix.lower() in {
                    ".html", ".css", ".js", ".json", ".png", ".svg", ".ico", ".woff", ".woff2"})
                or local in {"config/default.json", ".env.example", "iniciar-tudo.bat", "scripts/pregacao.cmd"})
    if relative.startswith("pipeline/"):
        local = relative.removeprefix("pipeline/")
        return (local in {"pipeline.py", "prompt.txt", "config.example.json", "package.json",
                          "package-lock.json", "whatsapp/send.js", "README.md", "SOURCE.json"}
                or local.startswith("node_modules/"))
    runtime = relative.startswith(("runtime/python/", "runtime/browsers/")) or relative in {
        "runtime/node/node.exe", "runtime/ffmpeg/bin/ffmpeg.exe", "runtime/ffmpeg/bin/ffprobe.exe"}
    return runtime or relative.startswith("licenses/") or relative in {
        "Iniciar Pregacao.cmd", "Verificar Pacote.cmd", "Conectar WhatsApp.cmd", "Bandeja.ps1", "LEIA-ME.txt", "GUIA-INSTALACAO.md", "ACEITE_WINDOWS.md"}


def validated_files(bundle: Path) -> tuple[dict, list[str]]:
    root = bundle.resolve()
    marker = bundle / "package-manifest.json"
    if marker.is_symlink() or not marker.resolve().is_relative_to(root):
        raise ValueError("Link ou caminho fora do pacote")
    manifest = json.loads(marker.read_text(encoding="utf-8"))
    if manifest.get("name") != "PregacaoRecorder" or manifest.get("schema_version") != 1:
        raise ValueError("Manifesto de pacote invalido")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Manifesto sem inventario")
    for relative, expected in files.items():
        if not public_path(relative) or not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError("Inventario inclui caminho privado ou invalido")
        file = bundle / relative
        if not file.resolve().is_relative_to(root) or file.is_symlink():
            raise ValueError("Link ou caminho fora do pacote")
        if not file.is_file() or digest(file) != expected:
            raise ValueError("Arquivo do pacote ausente ou alterado: " + relative)
    required = {"Iniciar Pregacao.cmd", "Verificar Pacote.cmd", "gravador/app/launcher.py",
                "gravador/config/default.json", "runtime/python/python.exe"}
    if not required.issubset(files):
        raise ValueError("Pacote incompleto para instalacao")
    return manifest, sorted(files) + ["package-manifest.json"]


def inno_string(value: str) -> str:
    return value.replace('"', '""').replace("{", "{{")


def prepare_script(bundle: Path, work: Path, output: Path, *, smoke: bool = False) -> tuple[Path, str]:
    manifest, files = validated_files(bundle)
    version = str(manifest.get("version", ""))
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", version):
        raise ValueError("Versao invalida")
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    (work / "install-files.txt").write_text("\n".join(files) + "\n", encoding="utf-8-sig")
    entries = []
    for relative in files:
        parent = str(PurePosixPath(relative).parent).replace("/", "\\")
        destination = "{app}" if parent == "." else "{app}\\" + inno_string(parent)
        entries.append('Source: "' + inno_string(str(bundle / relative)) + '"; DestDir: "'
                       + destination + '"; Flags: ignoreversion')
    (work / "bundle-files.iss").write_text("\n".join(entries) + "\n", encoding="utf-8-sig")
    source = (ROOT / "packaging/installer.iss").read_text(encoding="utf-8-sig")
    defines = ('#define PackageVersion "' + version + '"\n'
               '#define InstallerOutput "' + inno_string(str(output)) + '"\n'
               '#define AutostartScript "' + inno_string(str(ROOT / "packaging/windows_autostart.ps1")) + '"\n'
               '#define AppIcon "' + inno_string(str(ROOT / "packaging/gerador-de-estudo.ico")) + '"\n')
    if smoke:
        defines += '#define SmokeTestBuild\n'
    script = work / "setup.iss"
    script.write_text(defines + source, encoding="utf-8-sig")
    return script, "Gerador de Estudo" + ("-smoke" if smoke else "")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--iscc", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "dist-pacote")
    parser.add_argument("--smoke-build", action="store_true", help="Compilar sem registro/atalho, para teste isolado")
    options = parser.parse_args(argv)
    compiler = options.iscc or Path(shutil.which("ISCC.exe") or "")
    if not compiler.is_file():
        parser.error("Informe --iscc com o compilador Inno Setup 7 (somente maquina de build)")
    output = options.output.resolve()
    script, name = prepare_script(options.bundle.resolve(), output / "installer-build", output, smoke=options.smoke_build)
    log = output / (name + ".build.log")
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run([str(compiler.resolve()), str(script)], stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError("Compilacao falhou; consultar " + str(log))
    executable = output / (name + ".exe")
    executable.with_suffix(".exe.sha256").write_text(digest(executable) + "  " + executable.name + "\n", encoding="utf-8")
    print("INSTALADOR:", executable)
    print("LOG:", log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
