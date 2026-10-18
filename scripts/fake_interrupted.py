"""Cria uma gravacao interrompida falsa para validar a interface de recuperacao."""
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import config  # noqa: E402
from app.db import db  # noqa: E402

sid = sys.argv[1] if len(sys.argv) > 1 else "20260929-093000-demo1"
root = config.recordings_root
session_dir = root / ".sessions" / sid
session_dir.mkdir(parents=True, exist_ok=True)

rate, channels, seconds = 44100, 2, 60
for index in (1, 2):
    size = seconds * rate * channels * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + size, b"WAVE", b"fmt ", 16, 1, channels,
        rate, rate * channels * 2, channels * 2, 16, b"data", size,
    )
    # 1/8 de "audio" real: suficiente para exercitar a deteccao sem gastar disco
    payload = b"\x00" * (size // 8)
    (session_dir / f"segment_{index:04d}.wav").write_bytes(header + payload)

db.create_session(
    {
        "id": sid,
        "started_at": time.time() - 250,
        "state": "RECORDING",   # o scan de boot converte em RECOVERY_REQUIRED
        "device": "hw:1,0",
        "format": "S16_LE",
        "sample_rate": rate,
        "channels": channels,
    }
)
db.update_session(sid, state="RECOVERY_REQUIRED", interrupted=1)
print("sessao falsa criada:", session_dir)
