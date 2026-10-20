"""Ambiente do pacote Windows; desenvolvimento continua usando a propria .venv."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
import secrets
import sys
import tempfile


def detect_package(recorder_root: Path | None = None) -> Path | None:
    """Reconhece apenas o layout instalado, nunca um caminho recebido do ambiente."""
    recorder = Path(recorder_root or Path(__file__).resolve().parent.parent).resolve()
    package = recorder.parent
    if recorder.name.casefold() != "gravador":
        return None
    marker = package / "package-manifest.json"
    if not marker.is_file():
        return None
    try:
        manifest = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("name") != "PregacaoRecorder":
        return None
    required = (recorder, package / "pipeline", package / "runtime" / "python",
                package / "runtime" / "node", package / "runtime" / "ffmpeg" / "bin",
                package / "runtime" / "browsers")
    return package if all(path.is_dir() for path in required) else None


def is_bundled() -> bool:
    return detect_package() is not None


def configuration_defaults(package: Path) -> dict[str, str]:
    """Somente caminhos locais: nenhuma credencial e levada ao pacote."""
    return {"estudos.python": sys.executable, "estudos.pasta": str(package / "pipeline")}


def _env_settings(path: Path) -> dict[str, str]:
    """Le somente os valores locais, com a mesma precedencia de load_env."""
    if not path.exists():
        return {}
    settings = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            settings.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return settings


@contextmanager
def _configuration_lock(package: Path):
    """Serializa o primeiro clique e os filhos antes de importar CONFIG."""
    folder = package / "gravador" / "config"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "initialization.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _initialize_config(package: Path, env_settings: dict[str, str]) -> None:
    """Preenche somente identidade ausente; preserva preferencias e caminhos."""
    folder = package / "gravador" / "config"
    target = folder / "config.json"
    existing = target.exists()
    explicit_id = (os.environ.get("PREGACAO_DEVICE_ID", "").strip()
                   or env_settings.get("PREGACAO_DEVICE_ID", "").strip())
    if explicit_id and not os.environ.get("PREGACAO_DEVICE_ID", "").strip():
        # load_env usa setdefault: um valor herdado vazio nao deve esconder
        # a escolha explicita feita no .env desta instalacao.
        os.environ["PREGACAO_DEVICE_ID"] = explicit_id
    if target.exists():
        settings = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            raise ValueError("Configuracao local deve ser um objeto JSON.")
        if explicit_id or str(settings.get("device_id", "") or "").strip():
            return
    else:
        settings = {"estudos": {key.partition(".")[2]: value
                               for key, value in configuration_defaults(package).items()}}
    if not explicit_id:
        # O hostname pode se repetir em maquinas clonadas ou em duas pastas.
        # A CONFIG existente permite trocar este ID ao substituir um PC antigo.
        settings["device_id"] = "pregacao-" + secrets.token_hex(8)
    # O link no mesmo volume publica o JSON completo atomicamente. Outra abertura
    # simultanea pode criar o destino primeiro; nesse caso seu arquivo e preservado.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".tmp",
                                         prefix="initial-config-", dir=folder,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(settings, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        if existing:
            os.replace(temporary, target)
        else:
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _initialize_secret(package: Path, env_settings: dict[str, str]) -> None:
    """Cria segredo de sessao apenas localmente, sem trocar PINs ou credenciais."""
    if os.environ.get("PREGACAO_SECRET", "").strip():
        return
    local_secret = env_settings.get("PREGACAO_SECRET", "").strip()
    if local_secret:
        os.environ["PREGACAO_SECRET"] = local_secret
        return
    target = package / "gravador" / ".env"
    contents = target.read_text(encoding="utf-8") if target.exists() else ""
    local_secret = secrets.token_urlsafe(32)
    lines = contents.splitlines(keepends=True)
    found = False
    for index, raw in enumerate(lines):
        if raw.strip().partition("=")[0].strip() == "PREGACAO_SECRET":
            lines[index] = "PREGACAO_SECRET=" + local_secret + "\n"
            found = True
    if not found:
        if contents and not contents.endswith(("\n", "\r")):
            lines.append("\n")
        lines.append("PREGACAO_SECRET=" + local_secret + "\n")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".tmp",
                                         prefix="initial-env-", dir=target.parent,
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write("".join(lines))
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    os.environ["PREGACAO_SECRET"] = local_secret


def prepare_environment(*, create_config: bool = False,
                        recorder_root: Path | None = None) -> Path | None:
    """Prepara processos atuais/filhos antes de importar configuracao ou servicos."""
    package = detect_package(recorder_root)
    if package is None:
        return None
    recorder = package / "gravador"
    runtime = package / "runtime"
    os.environ["PREGACAO_HOME"] = str(recorder)
    os.environ["PREGACAO_BUNDLED_ROOT"] = str(package)
    os.environ["PREGACAO_NODE"] = str(runtime / "node" / "node.exe")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(runtime / "browsers")
    # Um atalho iniciado por um terminal de desenvolvimento pode herdar os
    # homes da origem. O pacote sempre usa seus proprios dados e autenticacao.
    os.environ["PREGACAO_PIPELINE_HOME"] = str(package / "pipeline")
    os.environ["NOTEBOOKLM_HOME"] = str(recorder / "data" / "notebooklm")
    directories = (runtime / "python", runtime / "python" / "Scripts",
                   runtime / "node", runtime / "ffmpeg" / "bin")
    parts = [str(path) for path in directories]
    parts.extend(os.environ.get("PATH", "").split(os.pathsep))
    seen = set()
    selected = []
    for part in parts:
        key = os.path.normcase(os.path.normpath(part)) if part else ""
        if key and key not in seen:
            seen.add(key)
            selected.append(part)
    os.environ["PATH"] = os.pathsep.join(selected)
    os.environ.pop("VIRTUAL_ENV", None)
    if create_config:
        with _configuration_lock(package):
            from .portable_state import relocate

            relocate(package)
            env_settings = _env_settings(recorder / ".env")
            _initialize_config(package, env_settings)
            _initialize_secret(package, env_settings)
    return package
