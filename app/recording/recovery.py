"""Deteccao e reparo de gravacoes interrompidas por queda de energia.

Estrategia:
  1. toda sessao comeca gravando os segmentos em ``recordings/.sessions/<id>``
     e e registrada no SQLite ANTES da primeira amostra ser capturada;
  2. ao subir, qualquer sessao ainda marcada como RECORDING significa que o
     sistema morreu no meio da gravacao;
  3. os segmentos sao verificados/corrigidos (cabecalho WAV pode estar truncado);
  4. NADA e apagado automaticamente - o usuario escolhe RECUPERAR ou DESCARTAR
     pela interface web.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..audio import wav
from ..logging_setup import get
from .consolidate import segment_list
log = get("recovery")

META_FILE = "session.json"


def write_meta(session_dir: Path, data: Dict[str, Any]) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    tmp = session_dir / (META_FILE + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(session_dir / META_FILE)


def read_meta(session_dir: Path) -> Optional[Dict[str, Any]]:
    path = session_dir / META_FILE
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def repair_segments(session_dir: Path, sample_rate: int, channels: int) -> Dict[str, Any]:
    """Corrige cabecalhos de segmentos truncados e mede a duracao recuperavel."""
    segments = segment_list(session_dir)
    repaired = 0
    total_bytes = 0
    duration = 0.0
    valid = 0
    surviving = 0
    for seg in segments:
        size = seg.stat().st_size
        if size <= wav.HEADER_SIZE:
            try:
                seg.unlink()
            except OSError:
                pass
            continue
        surviving += 1
        info = wav.read_info(seg)
        expected = info["data_size"] + wav.HEADER_SIZE if info else -1
        if info is None or abs(expected - size) > 1024:
            # segmento truncado: o ultimo write nao atualizou o cabecalho
            wav.repair(seg, sample_rate, channels)
            repaired += 1
        info2 = wav.read_info(seg)
        if info2:
            valid += 1
            total_bytes += info2["data_size"]
            duration += info2["duration"]
    return {
        "segments": surviving,
        "valid_segments": valid,
        "repaired": repaired,
        "bytes": total_bytes,
        "duration": duration,
    }


def scan(db, recordings_root: Path) -> List[Dict[str, Any]]:
    """Retorna as gravacoes interrompidas aguardando decisao do usuario."""
    found: List[Dict[str, Any]] = []

    for sess in db.sessions_in_state("RECORDING", "ERROR"):
        session_dir = Path(recordings_root) / ".sessions" / sess["id"]
        if not session_dir.exists() or not segment_list(session_dir):
            # sessao marcada como ativa mas sem segmentos: considera perdida
            if sess["state"] == "RECORDING":
                db.update_session(sess["id"], state="ERROR", error="sem segmentos encontrados")
            continue
        info = repair_segments(
            session_dir,
            int(sess.get("sample_rate") or 44100),
            int(sess.get("channels") or 2),
        )
        if info["segments"] == 0:
            db.update_session(sess["id"], state="ERROR", error="nenhum audio recuperavel")
            continue
        db.update_session(
            sess["id"],
            state="RECOVERY_REQUIRED",
            interrupted=1,
            segments=info["segments"],
            bytes=info["bytes"],
            duration_secs=info["duration"],
        )
        found.append(
            {
                "id": sess["id"],
                "started_at": sess["started_at"],
                "dir": str(session_dir),
                "reason": "queda_de_energia",
                **info,
            }
        )
        log.warning(
            "gravacao interrompida detectada: %s (%.1fs, %d segmentos)",
            sess["id"], info["duration"], info["segments"],
        )

    # diretorios orfaos (banco perdido, mas audio presente)
    sessions_root = recordings_root / ".sessions"
    if sessions_root.exists():
        known = {item["id"] for item in found}
        for child in sorted(sessions_root.iterdir()):
            if not child.is_dir() or child.name in known:
                continue
            if db.get_session(child.name):
                continue
            meta = read_meta(child) or {}
            rate = int(meta.get("sample_rate") or 44100)
            channels = int(meta.get("channels") or 2)
            info = repair_segments(child, rate, channels)
            if info["segments"] == 0:
                continue
            started = meta.get("started_at") or child.stat().st_ctime
            db.create_session(
                {
                    "id": child.name,
                    "started_at": started,
                    "state": "RECOVERY_REQUIRED",
                    "device": meta.get("device"),
                    "format": meta.get("format"),
                    "sample_rate": rate,
                    "channels": channels,
                    "segments": info["segments"],
                    "bytes": info["bytes"],
                    "duration_secs": info["duration"],
                    "interrupted": 1,
                }
            )
            found.append(
                {
                    "id": child.name,
                    "started_at": started,
                    "dir": str(child),
                    "reason": "sessao_orfa",
                    **info,
                }
            )
            log.warning("sessao orfa encontrada: %s", child.name)

    found.sort(key=lambda item: item.get("started_at") or 0, reverse=True)
    return found


def discard(db, session_id: str, recordings_root: Path) -> bool:
    """Descarta uma gravacao interrompida. Nunca e chamado automaticamente."""
    session_dir = recordings_root / ".sessions" / session_id
    removed = 0
    if session_dir.exists():
        for seg in segment_list(session_dir):
            try:
                seg.unlink()
                removed += 1
            except OSError:
                pass
        for extra in session_dir.glob("*"):
            try:
                extra.unlink()
            except OSError:
                pass
        try:
            session_dir.rmdir()
        except OSError:
            pass
    db.update_session(session_id, state="ERROR", error="descartada pelo usuario", interrupted=0)
    log.info("gravacao %s descartada (%d segmentos removidos)", session_id, removed)
    return True


def pending(db) -> List[Dict[str, Any]]:
    return db.sessions_in_state("RECOVERY_REQUIRED")


def age_label(started_at: Optional[float]) -> str:
    if not started_at:
        return "desconhecida"
    delta = max(0, time.time() - started_at)
    hours, rem = divmod(int(delta), 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d} atras"
