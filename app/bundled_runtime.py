"""Ambiente do pacote Windows; desenvolvimento continua usando a propria .venv."""
from __future__ import annotations

import json
import os
from pathlib import Path
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


def _initialize_config(package: Path) -> None:
    """Publica a primeira configuracao completa sem substituir arquivo existente."""
    folder = package / "gravador" / "config"
    target = folder / "config.json"
    if target.exists():
        return
    folder.mkdir(parents=True, exist_ok=True)
    settings = {"estudos": {key.partition(".")[2]: value
                           for key, value in configuration_defaults(package).items()}}
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
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
    if not os.environ.get("PREGACAO_PIPELINE_HOME", "").strip():
        os.environ["PREGACAO_PIPELINE_HOME"] = str(package / "pipeline")
    if not os.environ.get("NOTEBOOKLM_HOME", "").strip():
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
        _initialize_config(package)
    return package
