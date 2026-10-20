"""Monta instalador privado e portatil com o estado deste PC (nunca publicar)."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import subprocess

from build_bundle import ROOT, copy_file, copy_sources, sha256
from build_installer import inno_string, public_path, validated_files


APP_NAME = "PregacaoRecorder-Pessoal"
SKIP_RUNTIME = {"inicializacao.lock", "initialization.lock", "servidor.pid", "agente.pid"}


def _copy_tree(source: Path, target: Path, *, skip: set[str] = frozenset()) -> None:
    if not source.exists():
        return
    if not source.is_dir() or source.is_symlink():
        raise ValueError("Pasta de estado invalida: " + str(source))
    for item in sorted(source.rglob("*")):
        if item.is_symlink():
            raise ValueError("Estado contem link simbolico: " + str(item))
        if item.is_file() and item.name not in skip:
            copy_file(item, target / item.relative_to(source))


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON de configuracao invalido: " + str(path))
    return value


def _source_locations(notebooklm: Path | None) -> dict[str, Path]:
    config = _json(ROOT / "config/config.json")
    pipeline = Path(str(config.get("estudos", {}).get("pasta") or ""))
    recordings = Path(str(config.get("storage", {}).get("recordings_dir") or ROOT / "recordings"))
    note = notebooklm or Path(os.environ.get("NOTEBOOKLM_HOME") or Path.home() / ".notebooklm")
    locations = {"recorder": ROOT, "pipeline": pipeline,
                 "recordings": recordings, "notebooklm": note}
    for name, path in locations.items():
        if not path.is_absolute() or not path.is_dir():
            raise ValueError("Pasta de origem indisponivel: " + name)
        locations[name] = path.resolve()
    if not (pipeline / "pipeline.py").is_file():
        raise ValueError("Pipeline de origem indisponivel")
    return locations


def _backup_database(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError("Banco de origem ausente")
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(source), timeout=30)) as old:
        for table, column, done in (
            ("sessions", "state", {"COMPLETED", "ERROR", "INTERRUPTED"}),
            ("uploads", "status", {"DONE", "FAILED", "CANCELLED"}),
            ("jobs", "estado", {"CONCLUIDO", "FALHOU", "CANCELADO"}),
        ):
            values = {row[0] for row in old.execute(f"SELECT DISTINCT {column} FROM {table}")}
            if values - done:
                raise RuntimeError("Ha tarefas em andamento ou pendentes no banco: " + table)
        with closing(sqlite3.connect(str(target))) as new:
            old.backup(new)
            if new.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("A copia do banco nao passou na verificacao")


def _copy_private_state(target: Path, source: dict[str, Path], apk: Path) -> None:
    recorder = source["recorder"]
    pipeline = source["pipeline"]
    copy_file(recorder / ".env", target / "gravador/.env")
    _copy_tree(recorder / "config", target / "gravador/config",
               skip={"default.json", *SKIP_RUNTIME})
    _copy_tree(recorder / "data", target / "gravador/data",
               skip={"pregacao.db", "pregacao.db-wal", "pregacao.db-shm", *SKIP_RUNTIME})
    _backup_database(recorder / "data/pregacao.db", target / "gravador/data/pregacao.db")
    _copy_tree(source["recordings"], target / "gravador/recordings")
    _copy_tree(recorder / "recovery", target / "gravador/recovery")
    _copy_tree(recorder / "logs", target / "gravador/logs", skip=SKIP_RUNTIME)
    for name in ("config.json", ".env"):
        if (pipeline / name).is_file():
            copy_file(pipeline / name, target / "pipeline" / name)
    for name in ("whatsapp/auth", "audio", "gravacoes", "output", "logs", "recorder/recordings"):
        _copy_tree(pipeline / name, target / "pipeline" / name, skip=SKIP_RUNTIME)
    _copy_tree(source["notebooklm"], target / "gravador/data/notebooklm", skip=SKIP_RUNTIME)
    copy_file(apk, target / apk.name)
    marker = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
              "source_roots": {name: str(path) for name, path in source.items()}}
    (target / "portable-state.json").write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _public_snapshot(base: Path, target: Path, version: str) -> list[str]:
    manifest, files = validated_files(base)
    target.mkdir(parents=True)
    for relative in files:
        copy_file(base / relative, target / relative)
    # O runtime e imutavel, mas as fontes locais podem ter recebido a migracao
    # portatil depois da compilacao do pacote publico.
    copy_sources(ROOT, target)
    guide = (ROOT / "docs/GUIA_SSD_PORTATIL.md").read_text(encoding="utf-8")
    (target / "GUIA-INSTALACAO.md").write_text(guide, encoding="utf-8")
    (target / "LEIA-ME.txt").write_text(
        "Pregacao Recorder - edicao pessoal no SSD\n\n"
        "Execute Iniciar Pregacao.cmd nesta pasta. Leia GUIA-INSTALACAO.md.\n"
        "Config, contas, historico e gravacoes da origem estao incluidos.\n"
        "Use uma copia por vez com o mesmo ID MQTT.\n", encoding="utf-8")
    manifest["version"] = version
    manifest["personal_portable"] = True
    public = sorted(file.relative_to(target).as_posix() for file in target.rglob("*")
                    if file.is_file() and file.name != "package-manifest.json")
    if any(not public_path(relative) for relative in public):
        raise ValueError("Arquivo nao publico entrou no inventario base")
    manifest["files"] = {relative: sha256(target / relative) for relative in public}
    (target / "package-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validated_files(target)
    return public + ["package-manifest.json"]


def _private_manifest(target: Path) -> list[str]:
    private = sorted(file.relative_to(target).as_posix() for file in target.rglob("*")
                     if file.is_file() and not public_path(file.relative_to(target).as_posix())
                     and file.name != "personal-manifest.json")
    inventory = {relative: sha256(target / relative) for relative in private}
    (target / "personal-manifest.json").write_text(
        json.dumps({"schema_version": 1, "files": inventory}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return private + ["personal-manifest.json"]


def _file_entry(stage: Path, relative: str, *, private: bool) -> str:
    parent = str(PurePosixPath(relative).parent).replace("/", "\\")
    destination = "{app}" if parent == "." else "{app}\\" + inno_string(parent)
    flags = "onlyifdoesntexist" if private else "ignoreversion"
    return ('Source: "' + inno_string(str(stage / relative)) + '"; DestDir: "'
            + destination + '"; Flags: ' + flags)


def _build_installer(stage: Path, output: Path, version: str, public: list[str],
                     private: list[str], compiler: Path) -> Path:
    work = output / ("personal-build-" + version)
    work.mkdir()
    entries = [_file_entry(stage, name, private=False) for name in public]
    entries += [_file_entry(stage, name, private=True) for name in private]
    (work / "personal-files.iss").write_text("\n".join(entries) + "\n", encoding="utf-8-sig")
    source = (ROOT / "packaging/personal_portable.iss").read_text(encoding="utf-8-sig")
    defines = (f'#define PackageVersion "{version}"\n'
               f'#define InstallerOutput "{inno_string(str(output))}"\n')
    script = work / "setup.iss"
    script.write_text(defines + source, encoding="utf-8-sig")
    log = output / ("personal-installer-" + version + ".build.log")
    with log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run([str(compiler), str(script)], stdout=stream,
                                   stderr=subprocess.STDOUT)
    if completed.returncode:
        raise RuntimeError("Falha ao compilar instalador; consulte " + str(log))
    installer = output / ("PregacaoRecorder-Pessoal-Instalar-" + version + ".exe")
    installer.with_suffix(".exe.sha256").write_text(
        sha256(installer) + "  " + installer.name + "\n", encoding="utf-8")
    return installer


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path, help="pacote publico recente e validado")
    parser.add_argument("--output", type=Path, default=ROOT / "dist-pacote")
    parser.add_argument("--stage-root", type=Path, help="pasta curta para a montagem temporaria")
    parser.add_argument("--iscc", type=Path, required=True)
    parser.add_argument("--notebooklm-home", type=Path)
    options = parser.parse_args(argv)
    compiler = options.iscc.resolve()
    if not compiler.is_file():
        parser.error("Compilador Inno Setup ausente")
    apk = ROOT / "flutter/pregacao_controle/PregacaoControle-2.6.apk"
    if not apk.is_file():
        parser.error("APK atual ausente")
    source = _source_locations(options.notebooklm_home)
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    version = "portable-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Perfis de Chromium possuem caminhos relativos longos; a raiz curta evita
    # MAX_PATH no Windows, independentemente do local escolhido para os .exe.
    stage_root = options.stage_root.resolve() if options.stage_root else Path(output.anchor) / "PRP"
    stage_root.mkdir(parents=True, exist_ok=True)
    stage = stage_root / ("PRP-" + version)
    print("1/4 Copiando runtime e fontes", flush=True)
    public = _public_snapshot(options.base.resolve(), stage, version)
    print("2/4 Copiando dados e contas com backup SQLite", flush=True)
    _copy_private_state(stage, source, apk)
    private = _private_manifest(stage)
    print("3/4 Compilando instalador privado", flush=True)
    installer = _build_installer(stage, output, version, public, private, compiler)
    print("4/4 Artefatos prontos", flush=True)
    print("PASTA:", stage, flush=True)
    print("INSTALADOR:", installer, flush=True)
    print("ARQUIVOS PRIVADOS:", len(private), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
