from pathlib import Path

from app.audio import wav


def test_build_header_roundtrip(tmp_path: Path):
    p = tmp_path / "a.wav"
    p.write_bytes(wav.build_header(0, 44100, 2) + b"\x00" * 4096)
    info = wav.read_info(p)
    assert info is not None
    assert info["sample_rate"] == 44100
    assert info["channels"] == 2
    assert info["bits"] == 16


def test_repair_truncated_header(tmp_path: Path):
    """Simula corte de energia: dados presentes, cabecalho desatualizado."""
    p = tmp_path / "segmento.wav"
    payload = b"\x01\x02" * 22050  # 1 segundo mono 16bit @44100 -> 0.5s de dado
    p.write_bytes(wav.build_header(0, 44100, 1) + payload)

    before = wav.read_info(p)
    assert before["data_size"] == 0

    size = wav.repair(p, 44100, 1)
    after = wav.read_info(p)
    assert size == len(payload)
    assert after["data_size"] == len(payload)
    assert after["duration"] == len(payload) / (44100 * 2)


def test_is_valid_wav(tmp_path: Path):
    good = tmp_path / "ok.wav"
    good.write_bytes(wav.build_header(100, 48000, 1) + b"\x00" * 100)
    assert wav.is_valid_wav(good)

    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"lixo" * 100)
    assert not wav.is_valid_wav(bad)


def test_duration_of_empty_file(tmp_path: Path):
    p = tmp_path / "vazio.wav"
    p.write_bytes(wav.build_header(0, 44100, 2))
    assert wav.duration_of(p) == 0.0
