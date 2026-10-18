import time
from pathlib import Path

from app.storage import layout


def test_final_path_uses_date_structure(tmp_path: Path):
    started = time.mktime((2026, 9, 29, 13, 0, 0, 0, 0, -1))
    path = layout.final_path(tmp_path, started, ".mp3")
    assert path.parent.name == "09"
    assert path.parent.parent.name == "2026"
    assert path.name == "2026-09-29_130000.mp3"


def test_final_path_avoids_collision(tmp_path: Path):
    started = time.mktime((2026, 9, 29, 13, 0, 0, 0, 0, -1))
    first = layout.final_path(tmp_path, started, ".mp3")
    first.write_bytes(b"x")
    second = layout.final_path(tmp_path, started, ".mp3")
    assert first != second
    assert second.name == "2026-09-29_130000_1.mp3"


def test_safe_name_removes_problematic_chars():
    import re

    cleaned = layout.safe_name("Pregação #1 / àudio")
    assert re.fullmatch(r"[A-Za-z0-9._-]+", cleaned), cleaned
    assert " " not in cleaned
    assert layout.safe_name("   ") == "gravacao"
    assert layout.safe_name("2026-09-29_130000.mp3") == "2026-09-29_130000.mp3"


def test_disk_usage_reports_free_space(tmp_path: Path):
    usage = layout.disk_usage(tmp_path)
    assert usage["ok"] is True
    assert usage["free_mb"] >= 0
    assert usage["total_gb"] > 0


def test_has_space_threshold(tmp_path: Path):
    assert layout.has_space(tmp_path, 1) is True
    assert layout.has_space(tmp_path, 10 ** 9) is False


def test_list_recordings_sorted(tmp_path: Path):
    day = tmp_path / "2026" / "09"
    day.mkdir(parents=True)
    (day / "2026-09-29_130000.mp3").write_bytes(b"a" * 100)
    (day / "2026-09-29_150000.mp3").write_bytes(b"b" * 200)

    items = layout.list_recordings(tmp_path)
    assert len(items) == 2
    assert items[0]["name"] == "2026-09-29_150000.mp3"
    assert items[0]["bytes"] == 200


def test_prune_zero_keeps_everything(tmp_path: Path):
    day = tmp_path / "2026" / "09"
    day.mkdir(parents=True)
    (day / "antigo.mp3").write_bytes(b"x")
    assert layout.prune(tmp_path, 0) == 0
    assert (day / "antigo.mp3").exists()


def test_prune_removes_old_files(tmp_path: Path):
    day = tmp_path / "2026" / "09"
    day.mkdir(parents=True)
    old = day / "antigo.mp3"
    old.write_bytes(b"x")
    import os
    os.utime(old, (time.time() - 40 * 86400, time.time() - 40 * 86400))
    assert layout.prune(tmp_path, 30) == 1
    assert not old.exists()


def test_summarize(tmp_path: Path):
    summary = layout.summarize(tmp_path)
    assert summary["count"] == 0
    assert summary["latest"] is None
    assert summary["disk"]["ok"] is True
