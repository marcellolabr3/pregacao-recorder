"""Deteccao e teste de audio do Windows via FFmpeg/DirectShow."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

from ..logging_setup import get

# no Windows, subprocess sem esta flag abre janela de console visivel
_FLAGS_SUBPROCESS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

log = get("audio.device")

# Formatos reais da saida de `ffmpeg -list_devices true -f dshow`:
#   classico :  `[dshow @ 0000...]  "Nome"`       (dentro da secao de audio)
#   atual    :  `[in#0 @ 0000...] "Nome" (audio)` (marcado sem secao)
# "Alternative name" nunca casa (o aspo vem depois do texto).
DSHOW_LINE_RE = re.compile(
    r'^\[(?:dshow|in#\d+)[^\]]*\]\s+"(?P<name>[^"]+)"'
    r'(?:\s*\((?P<kind>audio|video)\))?\s*$'
)


def _run(cmd: List[str], timeout: int = 10) -> Optional[str]:
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
            creationflags=_FLAGS_SUBPROCESS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("falha ao executar %s: %s", " ".join(cmd), exc)
        return None
    return (proc.stdout or "") + (proc.stderr or "")


def _backend() -> str:
    return "dshow" if shutil.which("ffmpeg") else ""


def _list_dshow() -> List[Dict[str, Any]]:
    """Placas de audio listadas pelo ffmpeg (DirectShow, Windows)."""
    output = _run(
        ["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        timeout=15,
    ) or ""
    devices: List[Dict[str, Any]] = []
    secao_audio = False
    for line in output.splitlines():
        if "DirectShow audio devices" in line:
            secao_audio = True
            continue
        if "DirectShow video devices" in line:
            secao_audio = False
            continue
        match = DSHOW_LINE_RE.match(line.strip())
        if not match:
            continue  # alternative names e avisos ficam de fora
        kind = match.group("kind")
        if kind == "video":
            continue
        if kind is None and not secao_audio:
            continue  # formato classico: linha de video fora da secao de audio
        name = match.group("name").strip()
        devices.append(
            {
                "hw": name,  # o proprio nome vai em `-i audio=<nome>`
                "card": -1,
                "card_id": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40],
                "name": name,
                "usb": "usb" in name.lower(),
            }
        )
    return devices


def list_devices() -> List[Dict[str, Any]]:
    """Interfaces de captura do Windows."""
    return _list_dshow() if _backend() else []


def detect(configured: str = "auto") -> Dict[str, Any]:
    """Escolhe o dispositivo de captura.

    Ordem:
      1. valor explicito da configuracao (ex.: nome da interface no Windows);
      2. primeira placa USB detectada;
      3. primeira placa disponivel;
      4. ``default`` como ultimo recurso.
    """
    devices = list_devices()
    configured = (configured or "auto").strip()

    if configured and configured.lower() != "auto":
        alvo = configured.lower()
        for dev in devices:
            if dev["hw"].lower() == alvo or dev["card_id"].lower() == alvo:
                log.info("dispositivo configurado encontrado: %s (%s)", dev["hw"], dev["name"])
                return {**dev, "selected_by": "config"}
        log.warning(
            "dispositivo '%s' configurado nao encontrado; usando deteccao automatica",
            configured,
        )

    for dev in devices:
        if dev["usb"]:
            log.info("interface USB de audio detectada: %s (%s)", dev["hw"], dev["name"])
            return {**dev, "selected_by": "auto-usb"}

    if devices:
        log.info("nenhuma placa USB; usando primeira placa: %s", devices[0]["hw"])
        return {**devices[0], "selected_by": "auto-first"}

    log.error("nenhuma interface de audio encontrada (FFmpeg/DirectShow)")
    return {
        "hw": "default",
        "card": -1,
        "card_id": "default",
        "name": "Nenhuma interface encontrada",
        "usb": False,
        "selected_by": "fallback",
    }


_CACHE: Dict[str, Any] = {}
_CACHE_TS = 0.0


def detect_cached(configured: str = "auto", ttl: float = 30.0) -> Dict[str, Any]:
    """``detect()`` com cache curto: a interface quase nunca troca e a
    deteccao abre um processo (ffmpeg) - o painel e o agente
    consultam status a cada poucos segundos."""
    global _CACHE, _CACHE_TS
    chave = (configured or "auto").strip().lower()
    agora = time.time()
    if _CACHE and _CACHE.get("_chave") == chave and agora - _CACHE_TS < ttl:
        return {k: v for k, v in _CACHE.items() if k != "_chave"}
    det = detect(configured)
    _CACHE = {"_chave": chave, **det}
    _CACHE_TS = agora
    return det


def _cache_limpa() -> None:
    """Zera o cache de ``detect_cached`` (testes)."""
    global _CACHE, _CACHE_TS
    _CACHE = {}
    _CACHE_TS = 0.0


def capture_level(seconds: float = 2.0, device: Optional[str] = None) -> Dict[str, Any]:
    """Captura alguns segundos e mede o nivel (RMS/peak).

    Usado por `pregacao check` / tela de config para provar que o equipamento
    esta realmente recebendo audio da mesa.
    """
    backend = _backend()
    if backend == "dshow":
        alvo = (device or "").strip()
        if not alvo or alvo == "default":
            alvo = str(detect("auto").get("hw") or "")
        if not alvo or alvo == "default":
            return {"ok": False, "error": "nenhuma interface de audio encontrada"}
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "dshow",
            "-i", f"audio={alvo}",
            "-t", str(max(1, int(seconds))),
            "-ac", "1",
            "-ar", "44100",
            "-acodec", "pcm_s16le",
            "-f", "s16le",
            "pipe:1",
        ]
    else:
        return {"ok": False, "error": "ffmpeg nao instalado"}
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=seconds + 8,
            check=False,
            creationflags=_FLAGS_SUBPROCESS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": str(exc)}

    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or b"").decode(errors="replace").strip()}

    raw = proc.stdout or b""
    if not raw:
        return {"ok": False, "error": "nenhum dado capturado"}

    samples = []
    for i in range(0, len(raw) - 1, 2):
        val = int.from_bytes(raw[i:i + 2], "little", signed=True)
        samples.append(val)
    if not samples:
        return {"ok": False, "error": "buffer vazio"}

    peak = max(abs(v) for v in samples)
    rms = int((sum(v * v for v in samples) / len(samples)) ** 0.5)
    return {
        "ok": True,
        "samples": len(samples),
        "peak": peak,
        "peak_db": round(20 * __import__("math").log10(peak / 32768.0), 1) if peak else -90.0,
        "rms": rms,
        "silent": peak < 300,
    }
