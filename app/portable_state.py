"""Rebaseia dados pessoais quando o pacote portatil muda de unidade/pasta.

O marcador existe somente na edicao pessoal. O pacote publico continua com o
comportamento anterior e nao le dados da maquina usada para compila-lo.
"""
from __future__ import annotations

import json
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile


MARKER = "portable-state.json"
PATH_COLUMNS = (
    ("sessions", "final_path"),
    ("uploads", "file_path"),
    ("jobs", "audio_path"),
    ("jobs", "resultado"),
)


def _write_json(path: Path, value: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix="portable-", suffix=".tmp",
            dir=path.parent, delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _mapped_path(value: str, mappings: list[tuple[Path, Path]]) -> str:
    if not value:
        return value
    path = Path(value)
    if not path.is_absolute():
        return value
    for before, after in mappings:
        try:
            relative = path.relative_to(before)
        except ValueError:
            continue
        return str(after / relative)
    return value


def _mappings(package: Path, marker: dict) -> list[tuple[Path, Path]]:
    recorder = package / "gravador"
    source = marker.get("source_roots") or {}
    if not isinstance(source, dict):
        raise ValueError("Raizes do pacote portatil invalidas")
    destinations = {
        "recordings": recorder / "recordings",
        "pipeline": package / "pipeline",
        "recorder": recorder,
        "notebooklm": recorder / "data" / "notebooklm",
    }
    values = []
    for key, destination in destinations.items():
        raw = source.get(key)
        if raw:
            origin = Path(raw)
            if not origin.is_absolute():
                raise ValueError("Raiz anterior do pacote portatil invalida")
            values.append((origin, destination))
    previous = marker.get("last_root")
    if previous:
        origin = Path(previous)
        if not origin.is_absolute():
            raise ValueError("Local anterior do pacote portatil invalido")
        values.append((origin, package))
    values.sort(key=lambda pair: len(str(pair[0])), reverse=True)
    return values


def _rebase_config(package: Path, mappings: list[tuple[Path, Path]]) -> None:
    target = package / "gravador" / "config" / "config.json"
    if not target.is_file():
        return
    settings = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise ValueError("Configuracao portatil invalida")
    storage = settings.setdefault("storage", {})
    studies = settings.setdefault("estudos", {})
    if not isinstance(storage, dict) or not isinstance(studies, dict):
        raise ValueError("Caminhos da configuracao portatil invalidos")
    recordings = str(package / "gravador" / "recordings")
    target_pipeline = str(package / "pipeline")
    target_python = str(package / "runtime" / "python" / "python.exe")
    new_storage = _mapped_path(str(storage.get("recordings_dir") or ""), mappings)
    if new_storage and Path(new_storage).is_absolute() and new_storage != recordings:
        raise ValueError("Destino de gravacao externo ao SSD no pacote portatil")
    storage["recordings_dir"] = recordings
    studies["pasta"] = target_pipeline
    studies["python"] = target_python
    # O CLI do runtime privado deve ser chamado como modulo.
    studies.pop("notebooklm", None)
    _write_json(target, settings)


def _rebase_database(package: Path, mappings: list[tuple[Path, Path]]) -> None:
    target = package / "gravador" / "data" / "pregacao.db"
    if not target.is_file():
        return
    with closing(sqlite3.connect(str(target), timeout=30)) as conn:
        with conn:
            for table, column in PATH_COLUMNS:
                try:
                    rows = conn.execute(f"SELECT rowid, {column} FROM {table}").fetchall()
                except sqlite3.OperationalError as exc:
                    raise ValueError("Banco portatil sem estrutura esperada") from exc
                for rowid, previous in rows:
                    if not previous:
                        continue
                    current = _mapped_path(str(previous), mappings)
                    if current != previous:
                        conn.execute(
                            f"UPDATE {table} SET {column} = ? WHERE rowid = ?",
                            (current, rowid),
                        )


def relocate(package: Path) -> bool:
    """Ajusta caminhos conhecidos; retorna False no pacote publico."""
    package = package.resolve()
    path = package / MARKER
    if not path.is_file():
        return False
    marker = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(marker, dict) or marker.get("schema_version") != 1:
        raise ValueError("Marcador do pacote portatil invalido")
    if marker.get("last_root") == str(package):
        return True
    mappings = _mappings(package, marker)
    _rebase_config(package, mappings)
    _rebase_database(package, mappings)
    marker["last_root"] = str(package)
    _write_json(path, marker)
    return True
