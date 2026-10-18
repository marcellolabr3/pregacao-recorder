"""Persistencia em SQLite: sessoes de gravacao, fila de upload e notificacoes.

Um unico banco, com WAL, sobrevive a quedas de energia. E a fonte de verdade
para recuperacao e para a fila de uploads persistente.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from . import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,
    started_at     REAL NOT NULL,
    ended_at       REAL,
    state          TEXT NOT NULL,
    device         TEXT,
    format         TEXT,
    sample_rate    INTEGER,
    channels       INTEGER,
    segments       INTEGER NOT NULL DEFAULT 0,
    bytes          INTEGER NOT NULL DEFAULT 0,
    duration_secs  REAL NOT NULL DEFAULT 0,
    final_path     TEXT,
    final_bytes    INTEGER NOT NULL DEFAULT 0,
    drive_file_id  TEXT,
    drive_path     TEXT,
    error          TEXT,
    interrupted    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS uploads (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL,
    file_path      TEXT NOT NULL UNIQUE,
    status         TEXT NOT NULL DEFAULT 'PENDING',
    attempts       INTEGER NOT NULL DEFAULT 0,
    next_attempt   REAL NOT NULL DEFAULT 0,
    drive_file_id  TEXT,
    drive_path     TEXT,
    bytes          INTEGER NOT NULL DEFAULT 0,
    error          TEXT,
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       REAL NOT NULL,
    level    TEXT NOT NULL,
    kind     TEXT NOT NULL,
    message  TEXT NOT NULL,
    payload  TEXT
);

CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status, next_attempt);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
"""

# Guarda o "estado declarado" mesmo se o banco corromper no meio de uma escrita.
MUTEX_KEY = "runtime_state"


class Database:
    def __init__(self, file: Optional[Path] = None) -> None:
        self.file = Path(file) if file else paths.db_file()
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self.connection() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.file), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            with self._lock:
                yield conn
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # -- sessoes ---------------------------------------------------------
    def create_session(self, session: Dict[str, Any]) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                  (id, started_at, ended_at, state, device, format, sample_rate,
                   channels, segments, bytes, duration_secs, final_path,
                   final_bytes, drive_file_id, drive_path, error, interrupted)
                VALUES (:id, :started_at, :ended_at, :state, :device, :format,
                        :sample_rate, :channels, :segments, :bytes, :duration_secs,
                        :final_path, :final_bytes, :drive_file_id, :drive_path,
                        :error, :interrupted)
                """,
                {
                    "ended_at": None,
                    "device": None,
                    "format": None,
                    "sample_rate": None,
                    "channels": None,
                    "segments": 0,
                    "bytes": 0,
                    "duration_secs": 0,
                    "final_path": None,
                    "final_bytes": 0,
                    "drive_file_id": None,
                    "drive_path": None,
                    "error": None,
                    "interrupted": 0,
                    **session,
                },
            )

    def update_session(self, session_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = :{k}" for k in fields)
        with self.connection() as conn:
            conn.execute(
                f"UPDATE sessions SET {cols} WHERE id = :_id",
                {"_id": session_id, **fields},
            )

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_session(self, session_id: str) -> None:
        """Remove uma sessao vazia (nenhum audio capturado)."""
        with self.connection() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def sessions_in_state(self, *states: str) -> List[Dict[str, Any]]:
        marks = ",".join("?" for _ in states)
        with self.connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM sessions WHERE state IN ({marks}) ORDER BY started_at",
                states,
            ).fetchall()
        return [dict(r) for r in rows]

    # -- fila de upload --------------------------------------------------
    def enqueue_upload(self, session_id: str, file_path: str, size: int) -> int:
        now = time.time()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO uploads (session_id, file_path, status, bytes,
                                     created_at, updated_at)
                VALUES (?, ?, 'PENDING', ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (session_id, file_path, size, now, now),
            )
            row = conn.execute(
                "SELECT id FROM uploads WHERE file_path = ?", (file_path,)
            ).fetchone()
        return int(row["id"]) if row else 0

    def claim_pending_uploads(self, limit: int = 5) -> List[Dict[str, Any]]:
        now = time.time()
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM uploads
                 WHERE status = 'PENDING' AND next_attempt <= ?
                 ORDER BY created_at LIMIT ?
                """,
                (now, limit),
            ).fetchall()
            items = [dict(r) for r in rows]
            for item in items:
                conn.execute(
                    "UPDATE uploads SET status='RUNNING', updated_at=? WHERE id=?",
                    (now, item["id"]),
                )
        return items

    def update_upload(self, upload_id: int, **fields: Any) -> None:
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k} = :{k}" for k in fields)
        with self.connection() as conn:
            conn.execute(
                f"UPDATE uploads SET {cols} WHERE id = :_id",
                {"_id": upload_id, **fields},
            )

    def list_uploads(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM uploads ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def upload_stats(self) -> Dict[str, int]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM uploads GROUP BY status"
            ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    # -- notificacoes / log de eventos -----------------------------------
    def add_event(self, level: str, kind: str, message: str, payload: Any = None) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO events (ts, level, kind, message, payload) VALUES (?,?,?,?,?)",
                (time.time(), level, kind, message,
                 json.dumps(payload, ensure_ascii=False) if payload else None),
            )
            conn.execute(
                "DELETE FROM events WHERE id NOT IN "
                "(SELECT id FROM events ORDER BY ts DESC LIMIT 500)"
            )

    def list_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            if item.get("payload"):
                try:
                    item["payload"] = json.loads(item["payload"])
                except (ValueError, TypeError):
                    item["payload"] = None
            out.append(item)
        return out


db = Database()
