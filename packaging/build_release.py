"""Gera um instalador Windows limpo e o APK Android, lado a lado."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
FLUTTER_PROJECT = ROOT / "flutter/pregacao_controle"
BUILD_CACHE = ROOT / ".bundle-cache"
WORK_ROOT = ROOT / ".w"
SIGNING_KEY = ROOT / ".signing/debug.keystore"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def checked(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist-pacote")
    parser.add_argument("--cache", type=Path, default=BUILD_CACHE)
    parser.add_argument("--browser-cache", type=Path, default=BUILD_CACHE / "browsers")
    parser.add_argument("--iscc", type=Path,
                        default=ROOT / ".bundle-cache/inno-7.1.0/compiler/ISCC.exe")
    parser.add_argument("--flutter", type=Path,
                        default=Path(r"D:\Dev\flutter-sdk\flutter\bin\flutter.bat"))
    parser.add_argument("--use-built-apk", type=Path,
                        help="reusar um APK ja compilado e validado nesta maquina")
    options = parser.parse_args(argv)
    flutter = options.flutter.resolve()
    compiler = options.iscc.resolve()
    if (not options.use_built_apk and not flutter.is_file()) or not compiler.is_file():
        parser.error("Flutter ou Inno Setup ausente; informe --flutter e --iscc")
    if not options.use_built_apk and not SIGNING_KEY.is_file():
        parser.error("Chave de assinatura local ausente: .signing/debug.keystore")
    if sys.version_info[:2] != (3, 11) or os.name != "nt":
        parser.error("Use Python 3.11 no Windows x64")
    pubspec = (FLUTTER_PROJECT / "pubspec.yaml").read_text(encoding="utf-8")
    if not re.search(r"^version:\s*\d+\.\d+\.\d+\+\d+\s*$", pubspec, re.MULTILINE):
        parser.error("Versao Android invalida")
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache = options.cache.resolve()
    stage_root = WORK_ROOT.resolve()
    for folder in (cache / "pub", cache / "gradle", cache / "android", cache / "npm", stage_root):
        folder.mkdir(parents=True, exist_ok=True)
    build_env = dict(os.environ)
    build_env.update({
        "TEMP": str(stage_root), "TMP": str(stage_root), "TMPDIR": str(stage_root),
        "PUB_CACHE": str(cache / "pub"),
        "GRADLE_USER_HOME": str(cache / "gradle"),
        "ANDROID_USER_HOME": str(cache / "android"),
        "ANDROID_PREFS_ROOT": str(cache / "android"),
        "NPM_CONFIG_CACHE": str(cache / "npm"),
    })
    print("1/3 Preparando APK Android", flush=True)
    if not options.use_built_apk:
        checked([str(flutter), "pub", "get"], cwd=FLUTTER_PROJECT, env=build_env)
        checked([str(flutter), "build", "apk", "--release", "--no-pub"], cwd=FLUTTER_PROJECT, env=build_env)
    built_apk = (options.use_built_apk.resolve() if options.use_built_apk else
                 FLUTTER_PROJECT / "build/app/outputs/flutter-apk/app-release.apk")
    if not built_apk.is_file():
        raise FileNotFoundError("Flutter nao gerou o APK")
    print("2/3 Montando pacote Windows limpo", flush=True)
    with tempfile.TemporaryDirectory(prefix="b-", dir=stage_root) as work_name:
        work = Path(work_name)
        checked([sys.executable, "-B", str(ROOT / "packaging/build_bundle.py"),
                 "--output", str(work / "bundle"), "--cache", str(cache),
                 "--browser-cache", str(options.browser_cache.resolve()), "--skip-zip"], env=build_env)
        bundles = list((work / "bundle").glob("PregacaoRecorder-release-*"))
        if len(bundles) != 1 or not bundles[0].is_dir():
            raise RuntimeError("Pacote Windows nao foi identificado")
        checked([sys.executable, "-B", str(ROOT / "packaging/build_installer.py"),
                 str(bundles[0]), "--iscc", str(compiler), "--output", str(work / "installer")], env=build_env)
        installer = work / "installer/Gerador de Estudo.exe"
        if not installer.is_file():
            raise RuntimeError("Inno Setup nao gerou o instalador")
        print("3/3 Entregando os dois arquivos separados", flush=True)
        for source, name in ((installer, "Gerador de Estudo.exe"),
                             (built_apk, "Controle Android.apk")):
            target = output / name
            shutil.copy2(source, target)
            target.with_suffix(target.suffix + ".sha256").write_text(
                digest(target) + "  " + target.name + "\n", encoding="utf-8")
            print("PRONTO:", target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
