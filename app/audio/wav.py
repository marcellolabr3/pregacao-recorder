"""Utilitarios de cabecalho WAV (necessarios para recuperacao apos queda de energia)."""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Dict, Optional

HEADER_SIZE = 44


def build_header(data_size: int, sample_rate: int, channels: int, bits: int = 16) -> bytes:
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, block_align, bits)
        + b"data"
        + struct.pack("<I", data_size)
    )


def write_header(path: Path, data_size: int, sample_rate: int, channels: int, bits: int = 16) -> None:
    with open(path, "r+b") as fh:
        fh.write(build_header(data_size, sample_rate, channels, bits))


def read_info(path: Path) -> Optional[Dict]:
    try:
        with open(path, "rb") as fh:
            head = fh.read(44)
    except OSError:
        return None
    if len(head) < 44 or head[0:4] != b"RIFF" or head[8:12] != b"WAVE":
        return None
    bits = struct.unpack("<H", head[34:36])[0] or 16
    channels = struct.unpack("<H", head[22:24])[0] or 1
    rate = struct.unpack("<I", head[24:28])[0] or 44100
    data_size = struct.unpack("<I", head[40:44])[0]
    byte_rate = rate * channels * bits // 8
    duration = data_size / byte_rate if byte_rate else 0
    return {
        "sample_rate": rate,
        "channels": channels,
        "bits": bits,
        "data_size": data_size,
        "duration": duration,
    }


def repair(path: Path, sample_rate: int, channels: int, bits: int = 16) -> int:
    """Corrige o cabecalho de um segmento possivelmente truncado.

    Retorna a quantidade de bytes de payload corrigida.
    """
    size = path.stat().st_size
    data_size = max(0, size - HEADER_SIZE)
    write_header(path, data_size, sample_rate, channels, bits)
    return data_size


def duration_of(path: Path) -> float:
    info = read_info(path)
    return info["duration"] if info else 0.0


def is_valid_wav(path: Path) -> bool:
    return read_info(path) is not None
