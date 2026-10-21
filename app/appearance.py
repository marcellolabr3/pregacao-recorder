"""Imagens escolhidas pelo operador para a aparencia do painel local."""
from __future__ import annotations

from pathlib import Path

from . import paths

MAX_IMAGE_BYTES = 5 * 1024 * 1024
KINDS = {"logo", "background"}


def folder() -> Path:
    return paths.data_dir() / "appearance"


def image_path(kind: str) -> Path:
    if kind not in KINDS:
        raise ValueError("tipo de imagem invalido")
    return folder() / kind


def image_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def save(kind: str, data: bytes) -> None:
    path = image_path(kind)
    if not data or len(data) > MAX_IMAGE_BYTES or image_mime(data) is None:
        raise ValueError("Use PNG, JPEG ou WebP de ate 5 MB")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def remove(kind: str) -> None:
    image_path(kind).unlink(missing_ok=True)


def snapshot() -> dict[str, bool]:
    return {kind: image_path(kind).is_file() for kind in KINDS}
