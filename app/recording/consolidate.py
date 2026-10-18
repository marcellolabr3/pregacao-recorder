"""Consolidacao dos segmentos em um arquivo final unico.

Fluxo:
    segment_0001.wav ... segment_000N.wav
        -> (ffmpeg concat) -> 2026/09/2026-09-29_130000.mp3

O arquivo original (segmentos) so e removido DEPOIS de confirmar que a
conversao terminou com sucesso e que o arquivo final existe e tem tamanho > 0.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..audio import wav
from ..logging_setup import get

log = get("recording.consolidate")


def has_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg"))


def _concat_wav(target: Path, segments: List[Path], sample_rate: int, channels: int) -> None:
    """Junta os segmentos em um WAV unico sem depender do ffmpeg (fallback puro Python)."""
    with open(target, "wb") as out:
        out.write(wav.build_header(0, sample_rate, channels))
        total = 0
        for seg in segments:
            with open(seg, "rb") as fh:
                fh.seek(wav.HEADER_SIZE)
                while True:
                    chunk = fh.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
                    total += len(chunk)
        out.seek(0)
        out.write(wav.build_header(total, sample_rate, channels))


def consolidate(
    segments: List[Path],
    final_path: Path,
    sample_rate: int,
    channels: int,
    encoder: str = "mp3",
    bitrate: int = 128,
    progress: Optional[Callable[[float], None]] = None,
) -> Dict:
    """Gera o arquivo final. Lanca RuntimeError em falha; nunca apaga os segmentos."""
    segments = [Path(s) for s in segments if Path(s).exists()]
    if not segments:
        raise RuntimeError("nenhum segmento para consolidar")

    final_path.parent.mkdir(parents=True, exist_ok=True)
    use_mp3 = encoder == "mp3" and has_ffmpeg()
    # o temporario precisa manter a extensao final: o ffmpeg usa ela para
    # escolher o muxer ("...mp3.tmp" nao e um formato reconhecido).
    tmp_out = final_path.with_name(final_path.stem + ".tmp" + final_path.suffix)

    if use_mp3:
        list_file = final_path.with_suffix(".concat.txt")
        list_file.write_text(
            "".join(f"file '{s.resolve().as_posix()}'\n" for s in segments),
            encoding="utf-8",
        )
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-codec:a", "libmp3lame",
            "-b:a", f"{bitrate}k",
            "-ar", str(sample_rate),
            "-f", "mp3",
            str(tmp_out),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=7200, check=False)
        finally:
            try:
                list_file.unlink()
            except OSError:
                pass
        if proc.returncode != 0 or not tmp_out.exists() or tmp_out.stat().st_size == 0:
            raise RuntimeError(
                "ffmpeg falhou: " + ((proc.stderr or "").strip() or "saida vazia")
            )
        final_format = "mp3"
    else:
        if encoder == "mp3":
            log.warning("ffmpeg nao encontrado; mantendo WAV (arquivo maior, igualmente compativel)")
        wav_out = final_path if final_path.suffix.lower() == ".wav" else final_path.with_suffix(".wav")
        tmp_out = wav_out.with_name(wav_out.stem + ".tmp" + wav_out.suffix)
        _concat_wav(tmp_out, segments, sample_rate, channels)
        if tmp_out.stat().st_size <= wav.HEADER_SIZE:
            raise RuntimeError("conversao gerou arquivo vazio")
        final_path = wav_out
        final_format = "wav"

    if progress:
        progress(1.0)
    tmp_out.replace(final_path)
    size = final_path.stat().st_size
    log.info("arquivo final criado: %s (%d bytes, %s)", final_path, size, final_format)
    return {"path": final_path, "bytes": size, "format": final_format}


def verify(path: Path) -> Dict:
    """Verificacao de integridade do arquivo final antes do upload."""
    if not path.exists():
        return {"ok": False, "error": "arquivo nao existe"}
    size = path.stat().st_size
    if size <= 44:
        return {"ok": False, "error": "arquivo vazio ou truncado"}
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        with open(path, "rb") as fh:
            head = fh.read(3)
        if head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID3") or head[:3] == b"ID3":
            return {"ok": True, "bytes": size}
        # alguns encoders nao comecam exatamente em frame; aceita se houver dados
        return {"ok": True, "bytes": size, "warning": "cabecalho MP3 nao reconhecido"}
    if suffix == ".wav":
        info = wav.read_info(path)
        if not info:
            return {"ok": False, "error": "cabecalho WAV invalido"}
        if info["data_size"] + wav.HEADER_SIZE > size + 1024:
            return {"ok": False, "error": "cabecalho WAV inconsistente"}
        return {"ok": True, "bytes": size, "duration": info["duration"]}
    return {"ok": True, "bytes": size}


def cleanup_segments(session_dir: Path) -> int:
    """Remove os segmentos SOMENTE apos verificacao bem-sucedida."""
    removed = 0
    for seg in segment_list(session_dir):
        try:
            seg.unlink()
            removed += 1
        except OSError as exc:
            log.warning("nao foi possivel remover %s: %s", seg, exc)
    return removed


def segment_list(session_dir: Path) -> List[Path]:
    return sorted(Path(session_dir).glob("segment_*.wav"))
