"""Cria instalador Windows completo a partir da pasta pessoal atual no SSD."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from build_bundle import ROOT, copy_file, sha256
from build_installer import inno_string, public_path, validated_files
from build_personal_portable import _file_entry, _private_manifest
from verify_personal_portable import verify


TERMINAL_STATES = {
    "sessions": ("state", {"COMPLETED", "ERROR", "INTERRUPTED"}),
    "uploads": ("status", {"DONE", "FAILED", "CANCELLED"}),
    "jobs": ("estado", {"CONCLUIDO", "ERRO", "FALHOU", "CANCELADO"}),
}
TRANSIENT_NAMES = {
    "inicializacao.lock", "initialization.lock", "servidor.pid", "agente.pid",
    "pregacao.db-wal", "pregacao.db-shm", "SingletonLock", "SingletonCookie",
    "SingletonSocket", "DevToolsActivePort",
}
PRIVATE_TREES = (
    ("gravador", "config"), ("gravador", "data"),
    ("gravador", "recordings"), ("pipeline", "whatsapp", "auth"),
    ("pipeline", "audio"), ("pipeline", "gravacoes"),
    ("pipeline", "output"), ("pipeline", "recorder", "recordings"),
)
PRIVATE_FILES = {"gravador/.env", "pipeline/.env", "pipeline/config.json"}
NOTEBOOKLM_CACHE_DIRS = {
    "Cache", "Code Cache", "GPUCache", "DawnGraphiteCache",
    "DawnWebGPUCache", "GrShaderCache", "ShaderCache", "BrowserMetrics",
    "Crashpad", "component_crx_cache", "extensions_crx_cache",
    "GPUPersistentCache", "AutofillAiModelCache",
}


def _backup_database(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError("Banco pessoal ausente")
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(source), timeout=30)) as old:
        for table, (column, terminal) in TERMINAL_STATES.items():
            states = {row[0] for row in old.execute(f"SELECT DISTINCT {column} FROM {table}")}
            if states - terminal:
                raise RuntimeError("Ha tarefas em andamento ou pendentes: " + table)
        if old.execute(
            "SELECT COUNT(*) FROM whatsapp_sends WHERE status IN ('PENDENTE', 'ENVIANDO')"
        ).fetchone()[0]:
            raise RuntimeError("Ha envios WhatsApp pendentes")
        with closing(sqlite3.connect(str(target))) as new:
            old.backup(new)
            if new.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("A copia do banco nao passou na verificacao")


def _skip_directory(relative: Path) -> bool:
    parts = relative.parts
    if not any(parts[:len(tree)] == tree or tree[:len(parts)] == parts
               for tree in PRIVATE_TREES):
        return True
    return (parts[:3] == ("gravador", "data", "notebooklm")
            and any(part in NOTEBOOKLM_CACHE_DIRS for part in parts[3:]))


def _skip_file(relative: Path) -> bool:
    name = relative.name
    if (name in TRANSIENT_NAMES or name.startswith("Singleton")
            or name.lower().endswith((".log", ".tmp", ".lock", ".pid"))):
        return True
    if relative.as_posix() in {
        "package-manifest.json", "personal-manifest.json", "portable-state.json",
        "gravador/data/pregacao.db", "pipeline/audio/_teste_voz.wav",
    }:
        return True
    if "_teste_voz" in name and relative.parts[:2] == ("pipeline", "output"):
        return True
    parts = relative.parts
    if parts[:3] == ("gravador", "data", "notebooklm") and (
        any(part in NOTEBOOKLM_CACHE_DIRS for part in parts[3:])
        or name.startswith("BrowserMetrics")
    ):
        return True
    return (relative.as_posix() not in PRIVATE_FILES
            and not any(parts[:len(tree)] == tree for tree in PRIVATE_TREES))


def _copy_private_state(source: Path, target: Path, public: set[str], apk: Path) -> None:
    for directory, folders, files in os.walk(source, followlinks=False):
        parent = Path(directory).relative_to(source)
        kept = []
        for folder in sorted(folders):
            relative = parent / folder
            if _skip_directory(relative):
                continue
            if (source / relative).is_symlink():
                raise ValueError("Link em dados pessoais: " + str(relative))
            kept.append(folder)
        folders[:] = kept
        for name in sorted(files):
            relative = parent / name
            key = relative.as_posix()
            if key in public or _skip_file(relative):
                continue
            if public_path(key):
                raise ValueError("Arquivo publico fora do manifesto: " + key)
            item = source / relative
            if item.is_symlink():
                raise ValueError("Link em dados pessoais: " + key)
            copy_file(item, target / relative)

    _backup_database(source / "gravador/data/pregacao.db",
                     target / "gravador/data/pregacao.db")
    copy_file(apk, target / apk.name)

    marker = json.loads((source / "portable-state.json").read_text(encoding="utf-8"))
    if not isinstance(marker, dict) or marker.get("schema_version") != 1:
        raise ValueError("Marcador pessoal invalido")
    marker["last_root"] = str(source)
    (target / "portable-state.json").write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_snapshot(source: Path, stage: Path, version: str, apk: Path,
                     *, base: Path | None = None) -> tuple[list[str], list[str]]:
    source = source.resolve()
    base = (base or source).resolve()
    if not (source / "personal-manifest.json").is_file():
        raise ValueError("Selecione a pasta pessoal instalada, com contas e dados")
    private_marker = json.loads((source / "personal-manifest.json").read_text(encoding="utf-8"))
    if not isinstance(private_marker, dict) or private_marker.get("schema_version") != 1:
        raise ValueError("Manifesto pessoal invalido")
    source_manifest = json.loads((source / "package-manifest.json").read_text(encoding="utf-8"))
    manifest, files = validated_files(base)
    if (source_manifest.get("schema_version") != 1
            or source_manifest.get("name") != "PregacaoRecorder"
            or not source_manifest.get("personal_portable")
            or not isinstance(source_manifest.get("files"), dict)):
        raise ValueError("A origem nao e uma instalacao pessoal")
    if not apk.is_file():
        raise ValueError("APK atual ausente")
    if stage.resolve().is_relative_to(source) or stage.resolve().is_relative_to(base):
        raise ValueError("A montagem nao pode ficar dentro da pasta pessoal")
    stage.mkdir(parents=True, exist_ok=False)

    for relative in files:
        if relative != "package-manifest.json":
            copy_file(base / relative, stage / relative)
    guide = (ROOT / "docs/GUIA_INSTALACAO_LOCAL.md").read_text(encoding="utf-8")
    (stage / "GUIA-INSTALACAO.md").write_text(guide, encoding="utf-8")
    (stage / "LEIA-ME.txt").write_text(
        "Pregacao Recorder - instalacao completa no PC\n\n"
        "Execute Iniciar Pregacao.cmd na pasta instalada. Leia GUIA-INSTALACAO.md.\n"
        "Contas, historico, gravacoes e runtimes estao incluidos nesta copia local.\n"
        "Depois da instalacao, o programa funciona sem o SSD.\n"
        "Nao abra ao mesmo tempo a copia local e a copia do SSD: usam o mesmo ID MQTT.\n",
        encoding="utf-8")
    manifest["version"] = version
    manifest["personal_portable"] = True
    manifest["local_install"] = True
    manifest.pop("update_only", None)
    manifest["files"]["GUIA-INSTALACAO.md"] = sha256(stage / "GUIA-INSTALACAO.md")
    manifest["files"]["LEIA-ME.txt"] = sha256(stage / "LEIA-ME.txt")
    (stage / "package-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    public = sorted(manifest["files"]) + ["package-manifest.json"]

    _copy_private_state(source, stage, set(public), apk)
    private = _private_manifest(stage)
    validated_files(stage)
    verify(stage)
    return public, private


def build_installer(stage: Path, output: Path, version: str, public: list[str],
                    private: list[str], compiler: Path, *, smoke: bool = False) -> Path:
    work = output / ("personal-local-build-" + version + ("-smoke" if smoke else ""))
    work.mkdir(parents=True, exist_ok=False)
    entries = [_file_entry(stage, name, private=False) for name in public]
    entries += [_file_entry(stage, name, private=True) for name in private]
    (work / "personal-files.iss").write_text("\n".join(entries) + "\n", encoding="utf-8-sig")
    source = (ROOT / "packaging/personal_local.iss").read_text(encoding="utf-8-sig")
    defines = (f'#define PackageVersion "{version}"\n'
               f'#define InstallerOutput "{inno_string(str(output))}"\n'
               f'#define AutostartScript "{inno_string(str(ROOT / "packaging/windows_autostart.ps1"))}"\n')
    if smoke:
        defines += "#define SmokeTestBuild\n"
    script = work / "setup.iss"
    script.write_text(defines + source, encoding="utf-8-sig")
    name = "PregacaoRecorder-Completo-Instalar-" + version + ("-smoke" if smoke else "")
    installer = output / (name + ".exe")
    log = output / (name + ".build.log")
    with log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run([str(compiler), str(script)], stdout=stream,
                                   stderr=subprocess.STDOUT)
    if completed.returncode or not installer.is_file():
        raise RuntimeError("Falha ao compilar instalador; consulte " + str(log))
    installer.with_suffix(".exe.sha256").write_text(
        sha256(installer) + "  " + installer.name + "\n", encoding="utf-8")
    return installer


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="pasta pessoal atual no SSD")
    parser.add_argument("--base", type=Path, required=True,
                        help="pacote publico final validado")
    parser.add_argument("--apk", type=Path,
                        help="APK atual; por padrao, procura na pasta pessoal")
    parser.add_argument("--iscc", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist-pacote")
    parser.add_argument("--stage-root", type=Path, help="pasta curta fora do SSD")
    options = parser.parse_args(argv)
    compiler = options.iscc.resolve()
    if not compiler.is_file():
        parser.error("Compilador Inno Setup ausente")
    source = options.source.resolve()
    pubspec = (ROOT / "flutter/pregacao_controle/pubspec.yaml").read_text(encoding="utf-8")
    match = re.search(r"^version:\s*(\d+)\.(\d+)\.\d+\+\d+\s*$", pubspec, re.MULTILINE)
    if not match:
        parser.error("Versao Flutter invalida")
    expected_apk = f"PregacaoControle-{match[1]}.{match[2]}.apk"
    apk = (options.apk or source / expected_apk).resolve()
    if apk.name != expected_apk:
        parser.error("Informe o APK da versao Flutter atual: " + expected_apk)
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage_root = (options.stage_root or Path(output.anchor) / "PRL").resolve()
    stage_root.mkdir(parents=True, exist_ok=True)
    version = "local-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stage = stage_root / ("PRL-" + version)
    print("1/3 Conferindo e copiando instalacao pessoal", flush=True)
    public, private = prepare_snapshot(source, stage, version, apk,
                                       base=options.base.resolve())
    print("2/3 Compilando instalador completo", flush=True)
    installer = build_installer(stage, output, version, public, private, compiler)
    print("3/3 Artefato pronto", flush=True)
    print("INSTALADOR:", installer, flush=True)
    print("PUBLICOS:", len(public) - 1, "PRIVADOS:", len(private) - 1, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
