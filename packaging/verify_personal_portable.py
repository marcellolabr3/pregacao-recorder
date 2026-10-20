"""Confere integridade inicial do pacote pessoal sem abrir contas ou servicos."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

from build_bundle import sha256
from build_installer import public_path


def verify(root: Path) -> tuple[int, int]:
    root = root.resolve()
    public = json.loads((root / "package-manifest.json").read_text(encoding="utf-8"))
    private = json.loads((root / "personal-manifest.json").read_text(encoding="utf-8"))
    if not public.get("personal_portable") or private.get("schema_version") != 1:
        raise ValueError("Manifestos pessoais invalidos")
    for category, files in (("publico", public.get("files")), ("privado", private.get("files"))):
        if not isinstance(files, dict) or not files:
            raise ValueError("Inventario " + category + " vazio")
        for relative, expected in files.items():
            if (not isinstance(relative, str) or not isinstance(expected, str)
                    or len(expected) != 64 or "\\" in relative or ".." in PurePosixPath(relative).parts
                    or PurePosixPath(relative).is_absolute()
                    or public_path(relative) != (category == "publico")):
                raise ValueError("Entrada invalida no inventario " + category)
            file = root / relative
            if file.is_symlink() or not file.resolve().is_relative_to(root):
                raise ValueError("Arquivo fora da pasta instalada")
            if not file.is_file() or sha256(file) != expected:
                raise ValueError("Falha de integridade em " + category + ": " + relative)
    return len(public["files"]), len(private["files"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    args = parser.parse_args(argv)
    count = verify(args.package)
    print(f"Pacote integro: {count[0]} arquivos publicos e {count[1]} privados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
