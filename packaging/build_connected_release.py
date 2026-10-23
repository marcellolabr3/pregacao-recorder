"""Build a private Windows installer and Android APK with current connections.

The generic release remains public. This edition carries one person's current
broker settings, refreshable Google authorization, NotebookLM and WhatsApp
sessions when present, but no history, audio, database or old machine paths.
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
from build_release import FLUTTER_PROJECT, SIGNING_KEY


WORK_ROOT = ROOT / ".w"
CACHE = ROOT / ".bundle-cache"
CONNECTION_FILES = (
    "gravador/config/config.json",
    "gravador/config/google_token.json",
    "gravador/.env",
    "portable-state.json",
)
NOTEBOOKLM_TOKEN = "gravador/data/notebooklm/profiles/default/master_token.json"
NOTEBOOKLM_STORAGE = "gravador/data/notebooklm/profiles/default/storage_state.json"
NOTEBOOKLM_CONTEXT = "gravador/data/notebooklm/profiles/default/context.json"
WHATSAPP_AUTH = "pipeline/whatsapp/auth"
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
STUDY_KEYS = ("ativo", "whatsapp", "mind_map_enabled", "mind_map_prompt")


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
    studies = config.get("estudos")
    if isinstance(studies, dict):
        chosen = {key: studies[key] for key in STUDY_KEYS if key in studies}
        if chosen:
            private_config["estudos"] = chosen
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
    personal_files = list(CONNECTION_FILES)
    nlm_home = source / "data/notebooklm/profiles/default"
    if (source == ROOT.resolve() and
            not any((nlm_home / name).is_file() for name in
                    ("master_token.json", "storage_state.json"))):
        nlm_home = Path.home() / ".notebooklm/profiles/default"
    nlm_source = nlm_home / "master_token.json"
    if nlm_source.exists() or nlm_source.is_symlink():
        nlm = _read_json(nlm_source)
        if (nlm.get("version") != 1 or not isinstance(nlm.get("email"), str)
                or not nlm["email"].strip() or not isinstance(nlm.get("android_id"), str)
                or not nlm["android_id"].strip() or not isinstance(nlm.get("master_token"), str)
                or not nlm["master_token"].strip()):
            raise ValueError("Master token do NotebookLM invalido")
        nlm_target = bundle / NOTEBOOKLM_TOKEN
        nlm_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nlm_source, nlm_target)
        os.chmod(nlm_target, 0o600)
        personal_files.append(NOTEBOOKLM_TOKEN)
    for name, relative in (("storage_state.json", NOTEBOOKLM_STORAGE),
                           ("context.json", NOTEBOOKLM_CONTEXT)):
        original = nlm_home / name
        if original.exists() or original.is_symlink():
            if original.is_symlink() or not original.is_file():
                raise ValueError("Sessao NotebookLM invalida: " + name)
            target = bundle / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
            os.chmod(target, 0o600)
            personal_files.append(relative)

    pipeline_home = Path(env.get("PREGACAO_PIPELINE_HOME") or
                         str(config.get("estudos", {}).get("pasta") or ""))
    auth_source = pipeline_home / "whatsapp/auth" if str(pipeline_home) != "." else None
    if auth_source is not None and (auth_source / "creds.json").is_file():
        if any(path.is_symlink() for path in auth_source.rglob("*")):
            raise ValueError("Sessao WhatsApp contem link")
        auth_target = bundle / WHATSAPP_AUTH
        shutil.copytree(auth_source, auth_target)
        personal_files.append(WHATSAPP_AUTH)
    return tuple(personal_files)


def personalize_public_guide(bundle: Path, *, notebooklm: str = "none",
                             whatsapp: bool = False) -> None:
    """Make the installed instructions match this private edition."""
    guide = bundle / "GUIA-INSTALACAO.md"
    guide.write_text((ROOT / "docs/GUIA_INSTALACAO_CONECTADA.md").read_text(encoding="utf-8"),
                     encoding="utf-8")
    readme = bundle / "LEIA-ME.txt"
    readme.write_text(
        "Gerador de Estudo - instalador pessoal\n\n"
        "Inclui sua configuracao MQTT e a autorizacao existente do Google Drive.\n"
        + ({
            "durable": "Inclui o token duravel do NotebookLM para renovar o login automaticamente.\n",
            "session": "Inclui a sessao atual do NotebookLM; se expirar, renove o login no PC.\n",
            "none": "NotebookLM ainda precisa de um login proprio.\n",
        }[notebooklm])
        + ("Inclui a sessao existente do WhatsApp.\n" if whatsapp else
           "WhatsApp ainda precisa de leitura do QR no novo PC.\n")
        + "Nao inclui historico, gravacoes, backups nem dados do programa antigo.\n"
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
    """Add explicit Inno entries without putting secrets in the public manifest."""
    entries = []
    for relative in files:
        item = bundle / relative
        if relative == WHATSAPP_AUTH:
            if not item.is_dir() or item.is_symlink():
                raise ValueError("Sessao WhatsApp ausente ou link")
            entries.append(
                f'Source: "{inno_string(str(item))}\\*"; '
                'DestDir: "{app}\\pipeline\\whatsapp\\auth"; '
                'Flags: ignoreversion recursesubdirs createallsubdirs'
            )
            continue
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


def mobile_defines(bundle: Path) -> dict[str, str]:
    """Use the same saved MQTT identity as the installer, with operator auth."""
    settings = _read_json(bundle / CONNECTION_FILES[0])
    env = _env_values(bundle / CONNECTION_FILES[2])
    remote = settings.get("remote") or {}
    if not isinstance(remote, dict):
        raise ValueError("Configuracao MQTT invalida")
    mapping = {
        "host": "PREGACAO_REMOTE_HOST", "port": "PREGACAO_REMOTE_PORT",
        "tls": "PREGACAO_REMOTE_TLS", "device_id": "PREGACAO_DEVICE_ID",
        "operator_token": "PREGACAO_OPERATOR_TOKEN",
    }
    for key, name in mapping.items():
        if key in remote:
            value = remote[key]
            env[name] = ("1" if value else "0") if isinstance(value, bool) else str(value)
    host = env.get("PREGACAO_REMOTE_HOST", "").strip()
    device_id = env.get("PREGACAO_DEVICE_ID", "").strip()
    password = env.get("PREGACAO_OPERATOR_TOKEN", "").strip()
    if not host or not device_id or not password:
        raise ValueError("Host, ID ou token do operador MQTT ausente no APK pessoal")
    try:
        port = int(env.get("PREGACAO_REMOTE_PORT") or 8883)
    except ValueError as exc:
        raise ValueError("Porta MQTT invalida") from exc
    if not 1 <= port <= 65535:
        raise ValueError("Porta MQTT invalida")
    tls = str(env.get("PREGACAO_REMOTE_TLS", "1")).lower()
    return {
        "PREGACAO_MOBILE_HOST": host,
        "PREGACAO_MOBILE_PORT": str(port),
        "PREGACAO_MOBILE_TLS": "false" if tls in {"0", "false", "no", "off"} else "true",
        "PREGACAO_MOBILE_DEVICE_ID": device_id,
        "PREGACAO_MOBILE_USERNAME": "operador",
        "PREGACAO_MOBILE_PASSWORD": password,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apk-output", type=Path,
                        help="destino do APK pessoal (padrao: ao lado do instalador)")
    parser.add_argument("--bundle", type=Path,
                        help="retomar a partir de um pacote montado dentro do projeto")
    parser.add_argument("--allow-without-notebooklm", action="store_true",
                        help="gerar copia pessoal sem sessao do NotebookLM")
    parser.add_argument("--iscc", type=Path,
                        default=CACHE / "inno-7.1.0/compiler/ISCC.exe")
    parser.add_argument("--flutter", type=Path,
                        default=Path(r"D:\Dev\flutter-sdk\flutter\bin\flutter.bat"))
    options = parser.parse_args(argv)
    compiler = options.iscc.resolve()
    flutter = options.flutter.resolve()
    if (os.name != "nt" or sys.version_info[:2] != (3, 11) or
            not compiler.is_file() or not flutter.is_file() or not SIGNING_KEY.is_file()):
        parser.error("Build requer Windows x64, Python 3.11, Flutter, chave Android e Inno Setup")
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    build_env = dict(os.environ)
    build_env.pop("ANDROID_PREFS_ROOT", None)
    for name in ("pub", "gradle", "android", "npm"):
        (CACHE / name).mkdir(parents=True, exist_ok=True)
    build_env.update({
        "TEMP": str(WORK_ROOT), "TMP": str(WORK_ROOT), "TMPDIR": str(WORK_ROOT),
        "PUB_CACHE": str(CACHE / "pub"),
        "GRADLE_USER_HOME": str(CACHE / "gradle"),
        "ANDROID_USER_HOME": str(CACHE / "android"),
        "NPM_CONFIG_CACHE": str(CACHE / "npm"),
    })
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
            subprocess.run(command, cwd=ROOT, env=build_env, check=True)
            bundles = list(output.glob("PregacaoRecorder-release-*"))
            if len(bundles) != 1:
                raise RuntimeError("Pacote publico nao identificado")
            bundle = bundles[0]
        private = prepare_connection_overlay(options.source, bundle)
        if not any(name in private for name in (NOTEBOOKLM_TOKEN, NOTEBOOKLM_STORAGE)) and not options.allow_without_notebooklm:
            raise ValueError(
                "Sessao do NotebookLM ausente. Execute "
                "packaging/ativar_login_notebooklm.py ou use --allow-without-notebooklm."
            )
        notebooklm_mode = ("durable" if NOTEBOOKLM_TOKEN in private else
                           "session" if NOTEBOOKLM_STORAGE in private else "none")
        personalize_public_guide(bundle, notebooklm=notebooklm_mode,
                                 whatsapp=WHATSAPP_AUTH in private)
        install_output = work / "installer"
        script, _ = prepare_script(bundle, work / "script", install_output)
        write_private_entries(script, bundle, private)
        log = work / "inno-build.log"
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([str(compiler), str(script)], cwd=ROOT,
                                    env=build_env, stdout=stream, stderr=subprocess.STDOUT)
        executable = install_output / "Gerador de Estudo.exe"
        if result.returncode or not executable.is_file():
            raise RuntimeError("Compilacao pessoal falhou; consulte o log local")

        defines = work / "android-defines.json"
        defines.write_text(json.dumps(mobile_defines(bundle), ensure_ascii=False),
                           encoding="utf-8")
        os.chmod(defines, 0o600)
        subprocess.run([str(flutter), "pub", "get"], cwd=FLUTTER_PROJECT,
                       env=build_env, check=True)
        subprocess.run([str(flutter), "build", "apk", "--release", "--no-pub",
                        f"--dart-define-from-file={defines}"], cwd=FLUTTER_PROJECT,
                       env=build_env, check=True)
        apk = FLUTTER_PROJECT / "build/app/outputs/flutter-apk/app-release.apk"
        if not apk.is_file():
            raise RuntimeError("Flutter nao gerou o APK pessoal")

        destination = options.output.resolve()
        apk_destination = (options.apk_output or destination.with_name("Controle Android.apk")).resolve()
        if destination == apk_destination:
            raise ValueError("Instalador e APK precisam ter nomes diferentes")
        for original, target in ((executable, destination), (apk, apk_destination)):
            target.parent.mkdir(parents=True, exist_ok=True)
            staging = target.with_name(target.name + ".novo")
            shutil.copy2(original, staging)
            if sha256(staging) != sha256(original):
                raise RuntimeError("Copia pessoal falhou na verificacao")
        for target in (destination, apk_destination):
            target.with_name(target.name + ".novo").replace(target)
            target.with_suffix(target.suffix + ".sha256").write_text(
                sha256(target) + "  " + target.name + "\n", encoding="utf-8")
            print("ENTREGA PESSOAL PRONTA:", target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
