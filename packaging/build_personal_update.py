"""Compila atualizador publico da pasta pessoal existente, sem copiar dados privados."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

from build_bundle import ROOT, sha256
from build_installer import inno_string, validated_files


def prepare_update(bundle: Path, apk: Path, output: Path) -> tuple[Path, Path]:
    manifest, files = validated_files(bundle)
    if not apk.is_file() or apk.suffix.lower() != ".apk":
        raise ValueError("APK final ausente")
    version = "update-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work = output / ("personal-update-build-" + version)
    work.mkdir(parents=True)
    manifest["version"] = version
    manifest["personal_portable"] = True
    manifest["update_only"] = True
    marker = work / "package-manifest.json"
    marker.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    entries = []
    for relative in files:
        source = marker if relative == "package-manifest.json" else bundle / relative
        expected = sha256(marker) if relative == "package-manifest.json" else manifest["files"][relative]
        parent = str(PurePosixPath(relative).parent).replace("/", "\\")
        destination = "{app}" if parent == "." else "{app}\\" + inno_string(parent)
        entries.append('Source: "' + inno_string(str(source)) + '"; DestDir: "'
                       + destination + '"; Flags: ignoreversion; Check: NeedsUpdate('
                       + "'" + relative.replace("'", "''").replace("/", "\\") + "', '"
                       + expected + "')")
    entries.append('Source: "' + inno_string(str(apk))
                   + '"; DestDir: "{app}"; Flags: ignoreversion; Check: NeedsUpdate('
                   + "'" + apk.name.replace("'", "''") + "', '" + sha256(apk) + "')")
    (work / "update-files.iss").write_text("\n".join(entries) + "\n",
                                             encoding="utf-8-sig")
    inventory = [*files, apk.name]
    (work / "update-files.txt").write_text("\n".join(inventory) + "\n",
                                             encoding="utf-8-sig")
    source = (ROOT / "packaging/personal_update.iss").read_text(encoding="utf-8-sig")
    defines = (f'#define PackageVersion "{version}"\n'
               f'#define InstallerOutput "{inno_string(str(output))}"\n'
               f'#define AutostartScript "{inno_string(str(ROOT / "packaging/windows_autostart.ps1"))}"\n')
    script = work / "setup.iss"
    script.write_text(defines + source, encoding="utf-8-sig")
    return script, output / f"PregacaoRecorder-Pessoal-Atualizar-{version}.exe"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="pacote publico final validado")
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--iscc", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist-pacote")
    options = parser.parse_args(argv)
    compiler = options.iscc.resolve()
    if not compiler.is_file():
        parser.error("Compilador Inno Setup ausente")
    apk = options.apk.resolve()
    if not re.fullmatch(r"PregacaoControle-[0-9]+(?:\.[0-9]+)*\.apk", apk.name):
        parser.error("Nome de APK final invalido")
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    script, installer = prepare_update(options.bundle.resolve(), apk, output)
    log = installer.with_suffix(".build.log")
    with log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run([str(compiler), str(script)], stdout=stream,
                                   stderr=subprocess.STDOUT)
    if completed.returncode or not installer.is_file():
        raise RuntimeError("Falha ao compilar atualizador; consulte " + str(log))
    installer.with_suffix(".exe.sha256").write_text(
        sha256(installer) + "  " + installer.name + "\n", encoding="utf-8")
    print("ATUALIZADOR:", installer)
    print("LOG:", log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
