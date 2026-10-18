"""Organizacao e saude do armazenamento USB externo."""
from __future__ import annotations

import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..logging_setup import get

log = get("storage")

SAFE_RE = re.compile(r"[^0-9A-Za-z._-]+")


def safe_name(value: str) -> str:
    """Remove caracteres problematicos (espacos, acentos, simbolos)."""
    cleaned = SAFE_RE.sub("-", value.strip()).strip("-.")
    return cleaned or "gravacao"


def final_path(root: Path, started_at: float, ext: str = ".mp3") -> Path:
    """Gera ``root/2026/09/2026-09-29_130000.mp3`` a partir do inicio."""
    moment = datetime.fromtimestamp(started_at)
    directory = Path(root) / f"{moment:%Y}" / f"{moment:%m}"
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{moment:%Y-%m-%d_%H%M%S}"
    path = directory / f"{stem}{ext}"
    counter = 1
    while path.exists():
        path = directory / f"{stem}_{counter}{ext}"
        counter += 1
    return path


def disk_usage(path: Optional[Path] = None) -> Dict[str, Any]:
    target = Path(path) if path else Path.cwd()
    while not target.exists() and target != target.parent:
        target = target.parent
    try:
        usage = shutil.disk_usage(str(target))
    except OSError as exc:
        return {"ok": False, "error": str(exc), "path": str(target)}
    free_mb = usage.free // (1024 * 1024)
    return {
        "ok": True,
        "path": str(target),
        "total_gb": round(usage.total / (1024 ** 3), 1),
        "free_mb": free_mb,
        "free_gb": round(usage.free / (1024 ** 3), 1),
        "used_percent": round(100.0 * usage.used / usage.total, 1) if usage.total else 0.0,
    }


def has_space(path: Path, min_free_mb: int) -> bool:
    usage = disk_usage(path)
    if not usage.get("ok"):
        return False
    return usage["free_mb"] >= min_free_mb


def list_recordings(root: Path, limit: int = 50) -> List[Dict[str, Any]]:
    files: List[Path] = []
    try:
        for pattern in ("*/*/*.mp3", "*/*/*.wav", "*/*/*.m4a"):
            files.extend(root.glob(pattern))
    except OSError as exc:
        log.warning("falha ao listar gravacoes: %s", exc)
    files = [f for f in files if f.is_file()]
    files.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    out = []
    for path in files[:limit]:
        try:
            stat = path.stat()
        except OSError:
            continue
        out.append(
            {
                "name": path.name,
                "path": str(path),
                "relative": str(path.relative_to(root)) if path.is_relative_to(root) else path.name,
                "bytes": stat.st_size,
                "modified": stat.st_mtime,
            }
        )
    return out


def prune(root: Path, retention_days: int) -> int:
    """Aplica politica de retencao local. 0 = manter tudo."""
    if retention_days <= 0:
        return 0
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for item in list_recordings(root, limit=100000):
        if item["modified"] < cutoff:
            try:
                Path(item["path"]).unlink()
                removed += 1
            except OSError as exc:
                log.warning("falha ao aplicar retencao em %s: %s", item["path"], exc)
    if removed:
        log.info("retencao local: %d arquivos removidos (>%d dias)", removed, retention_days)
    return removed


def summarize(root: Path) -> Dict[str, Any]:
    items = list_recordings(root, limit=100000)
    return {
        "dir": str(root),
        "count": len(items),
        "bytes": sum(i["bytes"] for i in items),
        "latest": items[0] if items else None,
        "disk": disk_usage(root),
    }
