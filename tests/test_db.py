import time


def _session(sid="s1", state="RECORDING", started=None):
    return {
        "id": sid,
        "started_at": started or time.time(),
        "state": state,
        "device": "hw:1,0",
        "format": "S16_LE",
        "sample_rate": 44100,
        "channels": 2,
    }


def test_create_and_read_session(database):
    database.create_session(_session())
    row = database.get_session("s1")
    assert row["state"] == "RECORDING"
    assert row["sample_rate"] == 44100
    assert row["interrupted"] == 0


def test_update_session(database):
    database.create_session(_session())
    database.update_session("s1", state="COMPLETED", final_path="/x.mp3", final_bytes=10)
    row = database.get_session("s1")
    assert row["state"] == "COMPLETED"
    assert row["final_path"] == "/x.mp3"


def test_sessions_in_state(database):
    database.create_session(_session("a", "RECORDING"))
    database.create_session(_session("b", "COMPLETED"))
    assert [s["id"] for s in database.sessions_in_state("RECORDING")] == ["a"]
    assert len(database.sessions_in_state("RECORDING", "RECOVERY_REQUIRED")) == 1


def test_list_sessions_newest_first(database):
    database.create_session(_session("antiga", started=1000))
    database.create_session(_session("nova", started=9999))
    assert [s["id"] for s in database.list_sessions()] == ["nova", "antiga"]


def test_upload_queue_enqueue_and_claim(database):
    database.enqueue_upload("s1", "/tmp/a.mp3", 100)
    stats = database.upload_stats()
    assert stats["PENDING"] == 1

    claimed = database.claim_pending_uploads()
    assert len(claimed) == 1
    assert claimed[0]["file_path"] == "/tmp/a.mp3"
    # ja reivindicado: nao pode ser reenviado em duplicidade
    assert database.claim_pending_uploads() == []
    assert database.upload_stats()["RUNNING"] == 1


def test_upload_queue_is_idempotent(database):
    database.enqueue_upload("s1", "/tmp/a.mp3", 100)
    database.enqueue_upload("s1", "/tmp/a.mp3", 100)
    assert database.upload_stats()["PENDING"] == 1


def test_upload_backoff_respected(database):
    database.enqueue_upload("s1", "/tmp/a.mp3", 100)
    item = database.claim_pending_uploads()[0]
    database.update_upload(
        item["id"], status="PENDING", next_attempt=time.time() + 3600, attempts=1
    )
    assert database.claim_pending_uploads() == []
    assert database.upload_stats()["PENDING"] == 1


def test_upload_queue_survives_reopen(database):
    database.enqueue_upload("s1", "/tmp/persistente.mp3", 500)
    # simula reinicializacao: novo objeto apontando para o mesmo arquivo
    from app.db import Database

    reopened = Database(database.file)
    assert reopened.upload_stats()["PENDING"] == 1
    assert reopened.claim_pending_uploads()[0]["file_path"] == "/tmp/persistente.mp3"


def test_events_roundtrip(database):
    database.add_event("info", "gravacao_iniciada", "Gravacao iniciada", {"x": 1})
    items = database.list_events()
    assert items[0]["kind"] == "gravacao_iniciada"
    assert items[0]["payload"] == {"x": 1}
