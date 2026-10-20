"""Persistencia em SQLite: sessoes de gravacao, fila de upload e notificacoes.

Um unico banco, com WAL, sobrevive a quedas de energia. E a fonte de verdade
para recuperacao e para a fila de uploads persistente.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
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

CREATE TABLE IF NOT EXISTS jobs (
    job_id         TEXT PRIMARY KEY,
    recording_id   TEXT,
    audio_path     TEXT NOT NULL UNIQUE,
    drive_file_id  TEXT,
    metadados      TEXT,
    estado         TEXT NOT NULL DEFAULT 'PENDENTE',
    etapa          TEXT NOT NULL DEFAULT '',
    motivo         TEXT,
    resultado      TEXT,
    erro           TEXT,
    tentativas     INTEGER NOT NULL DEFAULT 0,
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL,
    started_at     REAL,
    finished_at    REAL
);

CREATE TABLE IF NOT EXISTS study_artifacts (
    job_id          TEXT PRIMARY KEY,
    pdf_path        TEXT,
    mind_map_path   TEXT,
    mind_map_error  TEXT,
    updated_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS whatsapp_sends (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL,
    recipient       TEXT NOT NULL,
    status          TEXT NOT NULL,
    message_id      TEXT,
    error           TEXT,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_whatsapp_sends_job ON whatsapp_sends(job_id, id);

-- S4: programacao de pregacoes (metadados unicos, no PC, refletidos no celular)
CREATE TABLE IF NOT EXISTS pregacoes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    data           TEXT NOT NULL,           -- AAAA-MM-DD
    horario        TEXT NOT NULL,           -- HH:MM
    pregador       TEXT NOT NULL,
    igreja         TEXT NOT NULL,
    texto_base     TEXT,                    -- referencia biblica
    tema           TEXT,                    -- tema da pregacao
    criado_em      REAL NOT NULL,
    atualizado_em  REAL NOT NULL,
    versao         INTEGER NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pregacoes_data_horario
    ON pregacoes(data, horario);

CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       REAL NOT NULL,
    level    TEXT NOT NULL,
    kind     TEXT NOT NULL,
    message  TEXT NOT NULL,
    payload  TEXT
);

CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status, next_attempt);
CREATE INDEX IF NOT EXISTS idx_jobs_estado ON jobs(estado, created_at);
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
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(study_artifacts)")}
            if "mind_map_error" not in columns:
                conn.execute("ALTER TABLE study_artifacts ADD COLUMN mind_map_error TEXT")

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

    # -- jobs do estudo (pipeline por gravacao) ---------------------------
    # Estados: PENDENTE / EXECUTANDO / CONCLUIDO / ERRO /
    #          AGUARDANDO_INTERVENCAO / CANCELADO
    # Toda troca de estado passa por transicao COM GUARDA no estado atual:
    # uma etapa concluida nunca "re-executa" nem e sobrescrita por uma
    # falha atrasada, mesmo apos reinicio do processo.
    def create_job(self, audio_path: str, metadados: Any = None) -> bool:
        """Cria o job de estudo de uma gravacao.

        Idempotente: o mesmo audio duas vezes rende UNICO job (UNIQUE em
        audio_path). Grava junto o recording_id e o drive_file_id que ja
        existirem - snapshot para as etapas seguintes nao dependerem de
        memoria. Devolve True somente quando um job foi realmente criado.
        """
        agora = time.time()
        job_id = uuid.uuid4().hex[:16]
        with self.connection() as conn:
            sess = conn.execute(
                "SELECT id, drive_file_id FROM sessions "
                "WHERE final_path = ? ORDER BY started_at DESC LIMIT 1",
                (audio_path,),
            ).fetchone()
            recording_id = sess["id"] if sess else None
            drive_file_id = None
            if sess and sess["drive_file_id"]:
                drive_file_id = sess["drive_file_id"]
            if not drive_file_id:
                up = conn.execute(
                    "SELECT drive_file_id FROM uploads "
                    "WHERE file_path = ? AND drive_file_id IS NOT NULL",
                    (audio_path,),
                ).fetchone()
                if up:
                    drive_file_id = up["drive_file_id"]
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO jobs
                  (job_id, recording_id, audio_path, drive_file_id, metadados,
                   estado, tentativas, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'PENDENTE', 0, ?, ?)
                """,
                (
                    job_id,
                    recording_id,
                    audio_path,
                    drive_file_id,
                    json.dumps(metadados, ensure_ascii=False)
                    if metadados is not None
                    else None,
                    agora,
                    agora,
                ),
            )
            return cur.rowcount == 1

    def claim_job(self) -> Optional[Dict[str, Any]]:
        """Pendente mais antigo -> EXECUTANDO (com guarda: uma unica
        reclamacao vence e a tentativa e contada)."""
        agora = time.time()
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE estado = 'PENDENTE' "
                "ORDER BY created_at, job_id LIMIT 1"
            ).fetchone()
            if not row:
                return None
            cur = conn.execute(
                """
                UPDATE jobs
                   SET estado = 'EXECUTANDO', etapa = 'PRE-FLIGHT',
                       tentativas = tentativas + 1,
                       started_at = COALESCE(started_at, :agora),
                       updated_at = :agora
                 WHERE job_id = :job_id AND estado = 'PENDENTE'
                """,
                {"job_id": row["job_id"], "agora": agora},
            )
            if cur.rowcount != 1:
                return None
            job = dict(row)
        job.update(
            estado="EXECUTANDO",
            etapa="PRE-FLIGHT",
            tentativas=int(job["tentativas"]) + 1,
        )
        return job

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def update_job(self, job_id: str, **fields: Any) -> None:
        """Campos avulsos (etapa, resultado, metadados...) SEM trocar o
        estado - estado so muda pelas transicoes com guarda abaixo."""
        if not fields:
            return
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k} = :{k}" for k in fields)
        with self.connection() as conn:
            conn.execute(
                f"UPDATE jobs SET {cols} WHERE job_id = :_id",
                {"_id": job_id, **fields},
            )

    def _transicao(
        self,
        job_id: str,
        estados_de: tuple,
        estado_para: str,
        **campos: Any,
    ) -> bool:
        marks = ", ".join(f":_e{i}" for i in range(len(estados_de)))
        params: Dict[str, Any] = {
            "_id": job_id,
            "_estado": estado_para,
            "_agora": time.time(),
        }
        params.update({f"_e{i}": e for i, e in enumerate(estados_de)})
        params.update(campos)
        sets = ", ".join(f"{k} = :{k}" for k in campos)
        sql = (
            "UPDATE jobs SET estado = :_estado, updated_at = :_agora"
            + (", " + sets if sets else "")
            + f" WHERE job_id = :_id AND estado IN ({marks})"
        )
        with self.connection() as conn:
            cur = conn.execute(sql, params)
            return cur.rowcount == 1

    def job_aguardar(self, job_id: str, motivo: str) -> bool:
        """EXECUTANDO -> AGUARDANDO_INTERVENCAO (pre-flight recusou:
        sessao expirada ou sem rede; o job e preservado, nao perdido)."""
        return self._transicao(
            job_id, ("EXECUTANDO",), "AGUARDANDO_INTERVENCAO", motivo=motivo
        )

    def job_concluir(
        self,
        job_id: str,
        resultado: Optional[str] = None,
        etapa: str = "FINAL",
    ) -> bool:
        # etapa final e a prova do ultimo marco: "FINAL" = WhatsApp
        # confirmado; "FINAL_SEM_ENVIO" = concluiu sem enviar (numero
        # nao configurado) - a barra nunca marca 100% sem envio real
        campos: Dict[str, Any] = {
            "etapa": etapa,
            "finished_at": time.time(),
            "erro": None,
            "motivo": None,
        }
        if resultado:
            campos["resultado"] = resultado
        return self._transicao(job_id, ("EXECUTANDO",), "CONCLUIDO", **campos)

    def job_falhar(self, job_id: str, erro: str) -> bool:
        return self._transicao(
            job_id, ("EXECUTANDO",), "ERRO", erro=erro, finished_at=time.time()
        )

    def job_reenfileirar(self, job_id: str) -> bool:
        """EXECUTANDO -> PENDENTE (recuperacao no boot apos crash)."""
        return self._transicao(job_id, ("EXECUTANDO",), "PENDENTE", motivo=None)

    def job_retomar(self) -> int:
        """Todos os AGUARDANDO_INTERVENCAO voltam a PENDENTE."""
        with self.connection() as conn:
            cur = conn.execute(
                "UPDATE jobs SET estado = 'PENDENTE', motivo = NULL, "
                "updated_at = ? WHERE estado = 'AGUARDANDO_INTERVENCAO'",
                (time.time(),),
            )
            return cur.rowcount

    def job_cancelar(self, job_id: str) -> bool:
        """So PENDENTE ou AGUARDANDO podem ser cancelados; um job em
        execucao termina o que esta fazendo antes de qualquer cancelamento."""
        return self._transicao(
            job_id,
            ("PENDENTE", "AGUARDANDO_INTERVENCAO"),
            "CANCELADO",
            finished_at=time.time(),
            motivo=None,
        )

    def jobs_em_execucao(self) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE estado = 'EXECUTANDO' "
                "ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def job_contagens(self) -> Dict[str, int]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT estado, COUNT(*) AS n FROM jobs GROUP BY estado"
            ).fetchall()
        return {r["estado"]: r["n"] for r in rows}

    def save_study_artifact(self, job_id: str, **fields: str) -> None:
        allowed = {key: value for key, value in fields.items()
                   if key in ("pdf_path", "mind_map_path", "mind_map_error")}
        if not allowed:
            return
        with self.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO study_artifacts(job_id, updated_at) VALUES (?, ?)",
                (job_id, time.time()),
            )
            sets = ", ".join(f"{key} = :{key}" for key in allowed)
            conn.execute(
                f"UPDATE study_artifacts SET {sets}, updated_at = :updated_at WHERE job_id = :job_id",
                {**allowed, "updated_at": time.time(), "job_id": job_id},
            )

    def study_artifact(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM study_artifacts WHERE job_id = ?", (job_id,)
            ).fetchone()
        return dict(row) if row else None

    def record_whatsapp_send(self, job_id: str, recipient: str, status: str,
                             *, message_id: str = "", error: str = "") -> int:
        now = time.time()
        with self.connection() as conn:
            cur = conn.execute(
                "INSERT INTO whatsapp_sends(job_id, recipient, status, message_id, error, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, recipient, status, message_id, error[:300], now, now),
            )
            return int(cur.lastrowid)

    def list_whatsapp_sends(self, job_id: str) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM whatsapp_sends WHERE job_id = ? ORDER BY id DESC",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_whatsapp_send(self, send_id: int, status: str,
                             *, message_id: str = "", error: str = "") -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE whatsapp_sends SET status = ?, message_id = ?, error = ?, "
                "updated_at = ? WHERE id = ?",
                (status, message_id, error[:300], time.time(), send_id),
            )

    def pending_whatsapp_sends(self) -> int:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM whatsapp_sends WHERE status = 'PENDENTE'"
            ).fetchone()
        return int(row["n"])

    def fail_interrupted_whatsapp_sends(self) -> int:
        with self.connection() as conn:
            cur = conn.execute(
                "UPDATE whatsapp_sends SET status = 'INCERTO_APOS_REINICIO', "
                "error = 'Processo interrompido; confira o recebimento antes de reenviar', "
                "updated_at = ? WHERE status = 'PENDENTE'",
                (time.time(),),
            )
            return cur.rowcount

    def job_motivo(self) -> str:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT motivo FROM jobs "
                "WHERE estado = 'AGUARDANDO_INTERVENCAO' "
                "AND motivo IS NOT NULL AND motivo != '' "
                "ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        return str(row["motivo"]) if row else ""

    # -- programacao de pregacoes (S4) ------------------------------------
    def create_pregacao(
        self,
        data: str,
        horario: str,
        pregador: str,
        igreja: str,
        texto_base: str = "",
        tema: str = "",
    ) -> int:
        """Insere uma nova pregacao. Retorna o id (PK). Levanta sqlite3.IntegrityError
        se ja existir mesma data+horario (index unico)."""
        agora = time.time()
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO pregacoes (data, horario, pregador, igreja, texto_base, tema,
                                       criado_em, atualizado_em, versao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (data, horario, pregador, igreja, texto_base, tema, agora, agora),
            )
            return cur.lastrowid

    def get_pregacao(self, pregacao_id: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM pregacoes WHERE id = ?", (pregacao_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_pregacao_por_data_horario(
        self, data: str, horario: str
    ) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM pregacoes WHERE data = ? AND horario = ?",
                (data, horario),
            ).fetchone()
        return dict(row) if row else None

    def list_pregacoes(
        self, data_de: Optional[str] = None, data_ate: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM pregacoes"
        params = []
        if data_de or data_ate:
            sql += " WHERE"
            if data_de:
                sql += " data >= ?"
                params.append(data_de)
            if data_ate:
                if data_de:
                    sql += " AND"
                sql += " data <= ?"
                params.append(data_ate)
        sql += " ORDER BY data DESC, horario DESC"
        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def update_pregacao(
        self, pregacao_id: int, *, expected_version: Optional[int] = None,
        **fields: Any,
    ) -> bool:
        """Atualiza com versao esperada quando informada pelo cliente."""
        if not fields:
            return False
        # so campos validos
        permitidos = {"data", "horario", "pregador", "igreja", "texto_base", "tema"}
        campos = {k: v for k, v in fields.items() if k in permitidos}
        if not campos:
            return False
        agora = time.time()
        campos["atualizado_em"] = agora
        # versao otimista: o WHERE checa a versao atual
        with self.connection() as conn:
            cur = conn.execute(
                "SELECT versao FROM pregacoes WHERE id = ?", (pregacao_id,)
            ).fetchone()
            if not cur:
                return False
            versao_atual = cur["versao"]
            if expected_version is not None and versao_atual != expected_version:
                return False
            campos["versao"] = versao_atual + 1
            set_clause = ", ".join(f"{k} = :{k}" for k in campos)
            cur = conn.execute(
                f"UPDATE pregacoes SET {set_clause} WHERE id = :_id AND versao = :_versao",
                {"_id": pregacao_id, "_versao": versao_atual, **campos},
            )
            return cur.rowcount > 0

    def delete_pregacao(
        self, pregacao_id: int, *, expected_version: Optional[int] = None,
    ) -> bool:
        with self.connection() as conn:
            if expected_version is None:
                cur = conn.execute(
                    "DELETE FROM pregacoes WHERE id = ?", (pregacao_id,)
                )
            else:
                cur = conn.execute(
                    "DELETE FROM pregacoes WHERE id = ? AND versao = ?",
                    (pregacao_id, expected_version),
                )
            return cur.rowcount > 0

    def snapshot_pregacao_para_job(self, data: str, horario: str) -> Optional[Dict[str, Any]]:
        """Converte a pregacao em dict JSON para gravar no jobs.metadados
        (congelamento no momento do estudo)."""
        p = self.get_pregacao_por_data_horario(data, horario)
        if not p:
            return None
        return {
            "pregacao_id": p["id"],
            "data": p["data"],
            "horario": p["horario"],
            "pregador": p["pregador"],
            "igreja": p["igreja"],
            "texto_base": p["texto_base"],
            "tema": p["tema"],
            "versao": p["versao"],
        }

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
