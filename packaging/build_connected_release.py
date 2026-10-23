"""Build a private Windows installer with only MQTT and Google Drive state.

The generic release remains public. This edition carries one person's current
broker settings and refreshable Google authorization, but no history, audio,
database, browser profile, or old machine paths.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from build_bundle import ROOT, sha256
from build_installer import inno_string, prepare_script, validated_files


WORK_ROOT = ROOT / ".w"
CACHE = ROOT / ".bundle-cache"
CONNECTION_FILES = (
    "gravador/config/config.json",
    "gravador/config/google_token.json",
    "gravador/.env",
    "portable-state.json",
)
REMOTE_ENV_KEYS = (
    "PREGACAO_REMOTE_HOST", "PREGACAO_REMOTE_PORT", "PREGACAO_REMOTE_TLS",
    "PREGACAO_REMOTE_ENABLED", "PREGACAO_DEVICE_ID",
    "PREGACAO_REMOTE_USERNAME", "PREGACAO_REMOTE_PASSWORD",
    "PREGACAO_OPERATOR_TOKEN", "PREGACAO_REMOTE_INTERVAL",
    "PREGACAO_REMOTE_KEEPALIVE", "PREGACAO_PIN", "PREGACAO_ADMIN_PIN",
)
REMOTE_CONFIG_KEYS = (
    "enabled", "host", "port", "tls", "username", "password",
    "device_id", "operator_token",
)
DRIVE_KEYS = (
    "enabled", "auto_upload", "folder_id", "folder_name", "keep_local",
    "retention_days", "client_id", "client_secret",
)


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Arquivo pessoal ausente ou link: " + path.name)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON pessoal invalido: " + path.name)
    return value


def _env_values(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(".env pessoal ausente ou link")
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in result:
            raise ValueError("Chave repetida no .env: " + key)
        result[key] = value.strip().strip('"').strip("'")
    return result


def prepare_connection_overlay(source: Path, bundle: Path) -> tuple[str, ...]:
    """Copy only effective connection identity into an already built bundle."""
    source, bundle = source.resolve(), bundle.resolve()
    if source == bundle:
        raise ValueError("A montagem deve ser diferente da origem dos dados")
    config = _read_json(source / "config/config.json")
    token = _read_json(source / "config/google_token.json")
    env = _env_values(source / ".env")
    drive = config.get("drive")
    remote = config.get("remote", {})
    if not isinstance(drive, dict) or not isinstance(remote, dict):
        raise ValueError("Configuracao Drive/MQTT invalida")
    if not all(isinstance(drive.get(key), str) and drive[key].strip()
               for key in ("client_id", "client_secret")):
        raise ValueError("Credenciais OAuth do Google ausentes")
    if not token.get("refresh_token") or any(
        token.get(key) != drive.get(key) for key in ("client_id", "client_secret")
    ):
        raise ValueError("Token Google ausente ou de outro cliente OAuth")
    effective = dict(env)
    mapping = {
        "enabled": "PREGACAO_REMOTE_ENABLED", "host": "PREGACAO_REMOTE_HOST",
        "port": "PREGACAO_REMOTE_PORT", "tls": "PREGACAO_REMOTE_TLS",
        "username": "PREGACAO_REMOTE_USERNAME", "password": "PREGACAO_REMOTE_PASSWORD",
        "device_id": "PREGACAO_DEVICE_ID", "operator_token": "PREGACAO_OPERATOR_TOKEN",
    }
    for key, env_key in mapping.items():
        if key in remote:
            value = remote[key]
            effective[env_key] = ("1" if value else "0") if isinstance(value, bool) else str(value)
    if not effective.get("PREGACAO_REMOTE_HOST", "").strip():
        raise ValueError("Broker MQTT ausente")
    if not effective.get("PREGACAO_DEVICE_ID", "").strip():
        raise ValueError("ID MQTT ausente")

    private_config = {
        "device_name": config.get("device_name", "Pulpito"),
        "drive": {key: drive[key] for key in DRIVE_KEYS if key in drive},
        "remote": {key: remote[key] for key in REMOTE_CONFIG_KEYS if key in remote},
    }
    if str(config.get("device_id") or "").strip():
        private_config["device_id"] = config["device_id"]
    config_target = bundle / CONNECTION_FILES[0]
    config_target.parent.mkdir(parents=True, exist_ok=True)
    config_target.write_text(json.dumps(private_config, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    token_target = bundle / CONNECTION_FILES[1]
    shutil.copy2(source / "config/google_token.json", token_target)
    env_target = bundle / CONNECTION_FILES[2]
    env_target.write_text("".join(f"{key}={env[key]}\n" for key in REMOTE_ENV_KEYS if key in env),
                          encoding="utf-8")
    # The existing first-launch relocation fills study/runtime paths for the
    # selected installation directory. No database or old path is included.
    marker = bundle / CONNECTION_FILES[3]
    marker.write_text(json.dumps({"schema_version": 1, "last_root": str(bundle),
                                  "source_roots": {}}, indent=2) + "\n", encoding="utf-8")
    for path in (config_target, token_target, env_target, marker):
        os.chmod(path, 0o600)
    return CONNECTION_FILES


def personalize_public_guide(bundle: Path) -> None:
    """Make the installed instructions match this private edition."""
    guide = bundle / "GUIA-INSTALACAO.md"
    guide.write_text((ROOT / "docs/GUIA_INSTALACAO_CONECTADA.md").read_text(encoding="utf-8"),
                     encoding="utf-8")
    readme = bundle / "LEIA-ME.txt"
    readme.write_text(
        "Gerador de Estudo - instalador pessoal\n\n"
        "Inclui sua configuracao MQTT e a autorizacao existente do Google Drive.\n"
        "Nao inclui historico, gravacoes, backups nem dados do programa antigo.\n"
        "Depois de instalar, escolha a interface de audio e a pasta de gravacao no novo PC.\n"
        "Leia GUIA-INSTALACAO.md. Mantenha este instalador privado.\n",
        encoding="utf-8",
    )
    marker = bundle / "package-manifest.json"
    manifest = _read_json(marker)
    for name in ("GUIA-INSTALACAO.md", "LEIA-ME.txt"):
        manifest["files"][name] = sha256(bundle / name)
    marker.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validated_files(bundle)


def write_private_entries(script: Path, bundle: Path, files: tuple[str, ...]) -> None:
    """Add four explicit Inno entries without putting secrets in the public manifest."""
    entries = []
    for relative in files:
        item = bundle / relative
        if not item.is_file() or item.is_symlink():
            raise ValueError("Arquivo de conexao ausente ou link")
        parent = str(Path(relative).parent).replace("/", "\\")
        destination = "{app}" if parent == "." else "{app}\\" + parent
        entries.append(
            f'Source: "{inno_string(str(item))}"; DestDir: "{destination}"; '
            f'DestName: "{item.name}"; Flags: ignoreversion'
        )
    (script.parent / "connection-files.iss").write_text("\n".join(entries) + "\n", encoding="utf-8-sig")
    script.write_text("#define ConnectedPersonalBuild\n" + script.read_text(encoding="utf-8-sig"),
                      encoding="utf-8-sig")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle", type=Path,
                        help="retomar a partir de um pacote montado dentro do projeto")
    parser.add_argument("--iscc", type=Path,
                        default=CACHE / "inno-7.1.0/compiler/ISCC.exe")
    options = parser.parse_args(argv)
    compiler = options.iscc.resolve()
    if os.name != "nt" or sys.version_info[:2] != (3, 11) or not compiler.is_file():
        parser.error("Build requer Windows x64, Python 3.11 e Inno Setup local")
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="conexoes-", dir=WORK_ROOT) as name:
        work = Path(name).resolve()
        if not work.is_relative_to(ROOT.resolve()):
            raise ValueError("Montagem fora de D:\\Dev")
        if options.bundle:
            bundle = options.bundle.resolve()
            if not bundle.is_relative_to(ROOT.resolve()) or not bundle.is_dir():
                raise ValueError("Pacote de retomada deve estar dentro do projeto")
        else:
            output = work / "bundle"
            command = [sys.executable, "-B", str(ROOT / "packaging/build_bundle.py"),
                       "--output", str(output), "--cache", str(CACHE),
                       "--browser-cache", str(CACHE / "browsers"), "--skip-zip"]
            subprocess.run(command, cwd=ROOT, check=True)
            bundles = list(output.glob("PregacaoRecorder-release-*"))
            if len(bundles) != 1:
                raise RuntimeError("Pacote publico nao identificado")
            bundle = bundles[0]
        personalize_public_guide(bundle)
        private = prepare_connection_overlay(options.source, bundle)
        install_output = work / "installer"
        script, _ = prepare_script(bundle, work / "script", install_output)
        write_private_entries(script, bundle, private)
        log = work / "inno-build.log"
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([str(compiler), str(script)], cwd=ROOT,
                                    stdout=stream, stderr=subprocess.STDOUT)
        executable = install_output / "Gerador de Estudo.exe"
        if result.returncode or not executable.is_file():
            raise RuntimeError("Compilacao pessoal falhou; consulte o log local")
        destination = options.output.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.with_name(destination.name + ".novo")
        shutil.copy2(executable, staging)
        if sha256(staging) != sha256(executable):
            raise RuntimeError("Copia pessoal falhou na verificacao")
        staging.replace(destination)
        print("INSTALADOR PESSOAL PRONTO:", destination, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
