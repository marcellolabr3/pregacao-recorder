import time
from pathlib import Path

from app.audio import wav
from app.recording import recovery
from app.recording.consolidate import cleanup_segments, consolidate, segment_list, verify


def _make_segment(path: Path, seconds: float = 0.2, rate: int = 44100, channels: int = 2,
                  bad_header: bool = False) -> Path:
    size = int(seconds * rate * channels * 2)
    header = wav.build_header(0 if bad_header else size, rate, channels)
    path.write_bytes(header + b"\x01\x02" * (size // 2))
    return path


def test_scan_detects_interrupted_session(database, tmp_path: Path):
    root = tmp_path / "recordings"
    session_dir = root / ".sessions" / "20260929-130000-ab12cd"
    session_dir.mkdir(parents=True)
    _make_segment(session_dir / "segment_0001.wav", bad_header=True)
    _make_segment(session_dir / "segment_0002.wav", bad_header=True)

    database.create_session(
        {
            "id": "20260929-130000-ab12cd",
            "started_at": time.time() - 120,
            "state": "RECORDING",
            "sample_rate": 44100,
            "channels": 2,
        }
    )

    found = recovery.scan(database, root)
    assert len(found) == 1
    item = found[0]
    assert item["segments"] == 2
    assert item["repaired"] == 2          # cabecalhos corrigidos
    assert item["duration"] > 0.3         # audio preservado
    assert database.get_session(item["id"])["state"] == "RECOVERY_REQUIRED"


def test_scan_marks_session_without_segments(database, tmp_path: Path):
    database.create_session({"id": "sem-arquivos", "started_at": 1.0, "state": "RECORDING"})
    found = recovery.scan(database, tmp_path / "recordings")
    assert found == []
    assert database.get_session("sem-arquivos")["state"] == "ERROR"


def test_scan_finds_orphan_directory(database, tmp_path: Path):
    """Banco perdido, mas o audio esta la."""
    root = tmp_path / "recordings"
    session_dir = root / ".sessions" / "orfao-1"
    session_dir.mkdir(parents=True)
    _make_segment(session_dir / "segment_0001.wav")
    recovery.write_meta(
        session_dir,
        {"started_at": time.time() - 60, "sample_rate": 44100, "channels": 2,
         "device": "hw:1,0"},
    )

    found = recovery.scan(database, root)
    assert len(found) == 1
    assert found[0]["reason"] == "sessao_orfa"
    assert database.get_session("orfao-1") is not None


def test_repair_segments_ignores_tiny_files(database, tmp_path: Path):
    root = tmp_path / "recordings"
    session_dir = root / ".sessions" / "lixo"
    session_dir.mkdir(parents=True)
    _make_segment(session_dir / "segment_0001.wav", seconds=0.1)
    (session_dir / "segment_0002.wav").write_bytes(b"RIFF")  # truncado de verdade

    info = recovery.repair_segments(session_dir, 44100, 2)
    assert info["segments"] == 1
    assert info["valid_segments"] == 1


def test_discard_never_runs_automatically(database, tmp_path: Path):
    root = tmp_path / "recordings"
    sid = "descartar-1"
    session_dir = root / ".sessions" / sid
    session_dir.mkdir(parents=True)
    _make_segment(session_dir / "segment_0001.wav")
    database.create_session({"id": sid, "started_at": 1.0, "state": "RECOVERY_REQUIRED"})

    # o scan nao remove nada
    recovery.scan(database, root)
    assert segment_list(session_dir)

    recovery.discard(database, sid, root)
    assert not segment_list(session_dir)
    assert database.get_session(sid)["state"] == "ERROR"


def test_pending_returns_only_recovery_required(database):
    database.create_session({"id": "x", "started_at": 1.0, "state": "RECOVERY_REQUIRED"})
    database.create_session({"id": "y", "started_at": 2.0, "state": "RECORDING"})
    assert [s["id"] for s in recovery.pending(database)] == ["x"]


# --------------------------------------------------------------------------
def test_consolidate_wav_without_ffmpeg(tmp_path: Path):
    seg = tmp_path / "sessao"
    seg.mkdir()
    _make_segment(seg / "segment_0001.wav", seconds=0.2)
    _make_segment(seg / "segment_0002.wav", seconds=0.2)

    out = tmp_path / "saida.wav"
    result = consolidate(segment_list(seg), out, 44100, 2, encoder="wav")
    assert result["path"].exists()
    assert result["bytes"] > wav.HEADER_SIZE + 4 * 8820
    info = wav.read_info(result["path"])
    assert info["duration"] > 0.35
    assert verify(result["path"])["ok"] is True


def test_consolidate_never_returns_empty(tmp_path: Path):
    seg = tmp_path / "vazio"
    seg.mkdir()
    try:
        consolidate([], tmp_path / "x.wav", 44100, 2, encoder="wav")
        assert False, "deveria falhar"
    except RuntimeError as exc:
        assert "segmento" in str(exc)


def test_verify_rejects_truncated_file(tmp_path: Path):
    p = tmp_path / "quebrado.wav"
    p.write_bytes(b"RIFFxxxxWAVE")
    assert verify(p)["ok"] is False


def test_verify_missing_file(tmp_path: Path):
    assert verify(tmp_path / "nao-existe.mp3")["ok"] is False


def test_cleanup_only_after_verification(tmp_path: Path):
    seg = tmp_path / "sessao"
    seg.mkdir()
    _make_segment(seg / "segment_0001.wav")
    files = segment_list(seg)
    result = consolidate(files, tmp_path / "final.wav", 44100, 2, encoder="wav")
    assert verify(result["path"])["ok"]
    removed = cleanup_segments(seg)
    assert removed == 1
    assert segment_list(seg) == []

