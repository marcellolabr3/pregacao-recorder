"""Captura de audio em segmentos.

O processo de captura e mantido vivo escrevendo PCM puro no stdout; o
processo Python quebra esse fluxo em segmentos WAV de ``segment_seconds``.

Backends: ``arecord`` (ALSA) no Linux/Raspberry e ``ffmpeg`` (DirectShow)
no Windows - o restante do modulo nao muda, o contrato e o mesmo.

Beneficios:
  * sem buracos entre segmentos (o fluxo e continuo);
  * se o equipamento cair com energia, apenas o ultimo segmento fica
    incompleto e o cabecalho e reparado na proxima inicializacao;
  * se a interface USB cair, o processo de captura e reiniciado com
    backoff sem encerrar a gravacao.
"""
from __future__ import annotations

import os
import signal
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..logging_setup import get
from . import wav

log = get("audio.recorder")

CHUNK = 16384  # 8192 amostras de 16 bits


class SegmentRecorder:
    """Grava segmentos ``segment_0001.wav`` ... dentro de ``session_dir``."""

    def __init__(
        self,
        session_dir: Path,
        device: str,
        sample_fmt: str = "S16_LE",
        sample_rate: int = 44100,
        channels: int = 2,
        segment_seconds: int = 60,
        on_event: Optional[Callable[[str, Dict], None]] = None,
    ) -> None:
        self.session_dir = Path(session_dir)
        self.device = device
        self.sample_fmt = sample_fmt
        self.sample_rate = sample_rate
        self.channels = channels
        self.segment_seconds = max(5, int(segment_seconds))
        self.on_event = on_event or (lambda kind, payload: None)

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()

        self.segments: List[Path] = []
        self.bytes_written = 0
        self.started_at: Optional[float] = None
        self.gaps = 0
        self.error: Optional[str] = None
        self._fh = None
        self._seg_index = 0
        self._seg_bytes = 0

    # ------------------------------------------------------------------
    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    @property
    def duration(self) -> float:
        return self.bytes_written / max(1, self.sample_rate * self.channels * 2)

    def start(self) -> None:
        if self.running:
            return
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._stop.clear()
        self.started_at = time.time()
        self._thread = threading.Thread(target=self._run, name="segment-recorder", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 15.0) -> None:
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.send_signal(signal.SIGINT)
            except (OSError, ValueError):
                # Windows nao aceita SIGINT via send_signal: encerra direto
                try:
                    proc.terminate()
                except OSError:
                    pass
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._thread:
            self._thread.join(timeout=timeout)
        self._close_segment()
        log.info("captura encerrada: %d segmentos, %d bytes", len(self.segments), self.bytes_written)

    # ------------------------------------------------------------------
    def _emit(self, kind: str, payload: Dict) -> None:
        try:
            self.on_event(kind, payload)
        except Exception:  # pragma: no cover - nunca deve derrubar a captura
            log.exception("erro no callback de evento")

    def _comando_captura(self) -> Optional[List[str]]:
        """Comando do backend de captura do sistema.

        ``arecord`` no Linux (o original) ou ``ffmpeg``/DirectShow no Windows;
        ``None`` quando nao ha ferramenta nenhuma instalada.
        """
        if shutil.which("arecord"):
            return [
                "arecord", "-q",
                "-D", self.device,
                "-f", self.sample_fmt,
                "-r", str(self.sample_rate),
                "-c", str(self.channels),
                "-t", "raw",
                "-",
            ]
        if shutil.which("ffmpeg"):
            return [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "dshow",
                "-i", f"audio={self.device}",
                "-ac", str(self.channels),
                "-ar", str(self.sample_rate),
                "-acodec", "pcm_s16le",
                "-f", "s16le",
                "pipe:1",
            ]
        return None

    def _spawn(self) -> Optional[subprocess.Popen]:
        cmd = self._comando_captura()
        if cmd is None:
            self.error = (
                "captura indisponivel: arecord (Linux) ou ffmpeg "
                "(Windows: winget install Gyan.FFmpeg) nao encontrado"
            )
            return None
        extra = (
            {"creationflags": subprocess.CREATE_NO_WINDOW}
            if os.name == "nt" else {}
        )
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
                **extra,
            )
        except OSError as exc:
            self.error = f"falha ao iniciar captura ({cmd[0]}): {exc}"
            return None
        log.info("captura iniciada (pid=%s, backend=%s, dispositivo=%s)",
                 proc.pid, cmd[0], self.device)
        return proc

    def _open_segment(self) -> None:
        self._seg_index += 1
        path = self.session_dir / f"segment_{self._seg_index:04d}.wav"
        fh = open(path, "wb+")
        fh.write(wav.build_header(0, self.sample_rate, self.channels))
        fh.flush()
        self._fh = fh
        self._seg_bytes = 0
        self.segments.append(path)
        self._emit("segment_started", {"segment": path.name, "index": self._seg_index})

    def _close_segment(self) -> None:
        fh = self._fh
        if fh is None:
            return
        try:
            fh.flush()
            os.fsync(fh.fileno())
            fh.seek(0)
            fh.write(wav.build_header(self._seg_bytes, self.sample_rate, self.channels))
            fh.close()
        except OSError as exc:
            log.error("falha ao fechar segmento: %s", exc)
        finally:
            self._fh = None
        log.info("segmento %04d fechado (%d bytes)", self._seg_index, self._seg_bytes)

    def _run(self) -> None:
        backoff = 1
        while not self._stop.is_set():
            proc = self._spawn()
            if proc is None:
                self.on_event("error", {"message": self.error or "captura indisponivel"})
                if self._stop.wait(backoff):
                    break
                backoff = min(backoff * 2, 30)
                continue

            self._proc = proc
            backoff = 1
            if self._fh is None:
                self._open_segment()

            assert proc.stdout is not None
            while not self._stop.is_set():
                data = proc.stdout.read(CHUNK)
                if not data:
                    break
                self._write(data)
                if self._seg_bytes >= self.segment_seconds * self.sample_rate * self.channels * 2:
                    self._close_segment()
                    if not self._stop.is_set():
                        self._open_segment()

            # fim do fluxo
            self._close_segment()
            if self._stop.is_set():
                break

            code = proc.poll()
            stderr = b""
            if proc.stderr:
                try:
                    stderr = proc.stderr.read() or b""
                except OSError:
                    pass
            msg = (stderr.decode(errors="replace") or "").strip().splitlines()
            self.gaps += 1
            self.error = msg[-1] if msg else f"captura terminou inesperadamente (codigo {code})"
            log.error("captura interrompida: %s", self.error)
            self._emit("capture_gap", {"message": self.error, "gaps": self.gaps})
            if self._stop.wait(backoff):
                break
            backoff = min(backoff * 2, 30)
            self._open_segment()

        self._close_segment()

    def _write(self, data: bytes) -> None:
        with self._lock:
            fh = self._fh
            if fh is None:
                return
            try:
                fh.write(data)
            except OSError as exc:
                self.error = f"falha de escrita: {exc}"
                log.error(self.error)
                self._emit("error", {"message": self.error})
                return
            self._seg_bytes += len(data)
            self.bytes_written += len(data)

    # ------------------------------------------------------------------
    def progress(self) -> Dict:
        with self._lock:
            return {
                "segments": len(self.segments),
                "current_segment": self._seg_index,
                "bytes": self.bytes_written,
                "duration": self.duration,
                "gaps": self.gaps,
                "device": self.device,
                "error": self.error,
            }

    def finalize_headers(self) -> None:
        """Garante que todos os segmentos tem cabecalho valido."""
        for path in sorted(self.session_dir.glob("segment_*.wav")):
            if not wav.is_valid_wav(path):
                wav.repair(path, self.sample_rate, self.channels)


def segment_files(session_dir: Path) -> List[Path]:
    return sorted(Path(session_dir).glob("segment_*.wav"))
