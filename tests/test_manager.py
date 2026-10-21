import time
from pathlib import Path

import pytest

from app.audio import wav
from app.recording.manager import ManagerError, RecordingManager
from app.states import InvalidTransition, State, state_machine


def _segment(path: Path, seconds: float = 1.0, bad_header: bool = False) -> Path:
    rate, channels = 44100, 2
    size = int(seconds * rate * channels * 2)
    path.write_bytes(wav.build_header(0 if bad_header else size, rate, channels)
                     + b"\x00" * (size // 4))
    return path


@pytest.fixture()
def manager(cfg, database):
    from app.upload.queue import UploadWorker

    return RecordingManager(cfg, database, UploadWorker(cfg, database))


def _make_interrupted(database, root: Path, sid="sessao-1"):
    session_dir = root / ".sessions" / sid
    session_dir.mkdir(parents=True)
    _segment(session_dir / "segment_0001.wav", bad_header=True)
    _segment(session_dir / "segment_0002.wav", bad_header=True)
    database.create_session(
        {
            "id": sid,
            "started_at": time.time() - 60,
            "state": "RECORDING",
            "sample_rate": 44100,
            "channels": 2,
        }
    )
    return session_dir


def test_status_promotes_pending_recovery(manager, database, recordings_root, fresh_state):
    _make_interrupted(database, recordings_root)
    from app.recording import recovery

    recovery.scan(database, recordings_root)

    # estado "sujo" vindo de uma falha anterior
    state_machine.set(State.ERROR, force=True)

    status = manager.status()
    assert status["state"] == State.RECOVERY_REQUIRED
    assert len(status["recovery"]) == 1
    assert status["recovery"][0]["duration"] > 0


def test_start_is_blocked_while_recovery_pending(manager, database, recordings_root, fresh_state):
    _make_interrupted(database, recordings_root)
    from app.recording import recovery

    recovery.scan(database, recordings_root)
    state_machine.set(State.RECOVERY_REQUIRED, force=True)

    with pytest.raises(ManagerError):
        manager.start()
    assert state_machine.state == State.RECOVERY_REQUIRED


def test_start_blocked_while_already_recording(manager, fresh_state):
    state_machine.set(State.RECORDING, force=True, session_id="x")
    with pytest.raises(ManagerError):
        manager.start()


def test_disco_indisponivel_impede_captura_e_nao_cria_sessao(manager, monkeypatch, fresh_state):
    from app.recording import manager as module
    monkeypatch.setattr(module.audio_device, "detect", lambda *_: {"hw": "USB", "card": -1, "selected_by": "config"})
    monkeypatch.setattr(module.destinos, "aviso", lambda *_: "Destino indisponivel")
    with pytest.raises(ManagerError, match="Destino indisponivel"):
        manager.start()
    assert manager.recorder is None


def test_stop_without_recorder_is_safe(manager, fresh_state):
    state_machine.set(State.RECORDING, force=True, session_id="x")
    with pytest.raises(ManagerError):
        manager.stop()


def test_cancel_discards_active_capture_without_study_or_upload(
        manager, database, recordings_root, fresh_state, monkeypatch):
    from app.recording import manager as module

    sid = "acidental"
    session_dir = recordings_root / ".sessions" / sid
    session_dir.mkdir(parents=True)
    (session_dir / "segment_0001.wav").write_bytes(b"audio de teste")
    database.create_session({"id": sid, "started_at": time.time(),
                             "state": State.RECORDING})

    class FakeRecorder:
        stopped = False

        def stop(self):
            self.stopped = True

    recorder = FakeRecorder()
    manager.recorder = recorder
    manager.session_id = sid
    state_machine.set(State.RECORDING, session_id=sid, force=True)
    monkeypatch.setattr(module.estudos, "enfileirar",
                        lambda *_: pytest.fail("cancelamento nao pode criar estudo"))
    result = manager.cancel()

    assert result["status"] == "DISCARDED"
    assert recorder.stopped
    assert not session_dir.exists()
    assert database.get_session(sid) is None
    with database.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM uploads").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    assert manager.recorder is None
    assert manager.session_id is None
    assert state_machine.snapshot()["session_id"] == ""
    assert state_machine.state == State.IDLE


def test_cancel_is_rejected_when_not_recording(manager, fresh_state):
    with pytest.raises(InvalidTransition):
        manager.cancel()


def test_cancel_cleanup_failure_keeps_session_for_recovery(
        manager, database, recordings_root, fresh_state, monkeypatch):
    from app.recording import manager as module

    sid = "falha-descarte"
    session_dir = recordings_root / ".sessions" / sid
    session_dir.mkdir(parents=True)
    (session_dir / "segment_0001.wav").write_bytes(b"audio")
    database.create_session({"id": sid, "started_at": time.time(),
                             "state": State.RECORDING})

    class FakeRecorder:
        def stop(self):
            pass

    manager.recorder = FakeRecorder()
    manager.session_id = sid
    state_machine.set(State.RECORDING, session_id=sid, force=True)
    monkeypatch.setattr(module.shutil, "rmtree",
                        lambda *_: (_ for _ in ()).throw(OSError("ocupado")))

    with pytest.raises(ManagerError, match="recuperacao"):
        manager.cancel()
    assert session_dir.exists()
    assert database.get_session(sid)["state"] == State.RECOVERY_REQUIRED
    assert state_machine.state == State.RECOVERY_REQUIRED


def test_discard_keeps_user_in_control(manager, database, recordings_root, fresh_state):
    session_dir = _make_interrupted(database, recordings_root, "vai-descartar")
    from app.recording import recovery

    recovery.scan(database, recordings_root)
    state_machine.set(State.RECOVERY_REQUIRED, force=True)

    manager.discard("vai-descartar")

    assert not (session_dir / "segment_0001.wav").exists()
    assert database.get_session("vai-descartar")["state"] == State.ERROR
    assert state_machine.state == State.IDLE
    assert manager.pending_recovery() == []


def test_discard_refused_for_normal_sessions(manager, database, recordings_root, fresh_state):
    database.create_session(
        {"id": "normal", "started_at": 1.0, "state": "COMPLETED",
         "sample_rate": 44100, "channels": 2}
    )
    with pytest.raises(ManagerError):
        manager.discard("normal")


def test_recover_refused_for_missing_session(manager, fresh_state):
    with pytest.raises(ManagerError):
        manager.recover("nao-existe")


def test_error_session_with_segments_is_recoverable(manager, database, recordings_root, fresh_state):
    """Uma falha de consolidacao nao pode deixar o audio preso em ERROR."""
    session_dir = _make_interrupted(database, recordings_root, "falhou")
    database.update_session("falhou", state="ERROR", error="ffmpeg quebrou")

    from app.recording import recovery

    found = recovery.scan(database, recordings_root)
    assert len(found) == 1
    assert (session_dir / "segment_0001.wav").exists()
    row = database.get_session("falhou")
    assert row["state"] == State.RECOVERY_REQUIRED
    assert row["interrupted"] == 1


def test_error_session_without_segments_is_ignored(database, recordings_root):
    database.create_session(
        {"id": "sem-audio", "started_at": 1.0, "state": "ERROR",
         "sample_rate": 44100, "channels": 2}
    )
    from app.recording import recovery

    assert recovery.scan(database, recordings_root) == []


def test_empty_recording_is_discarded_not_error(manager, database, recordings_root, fresh_state):
    """Finalizar em 0 bytes descarta a sessao e volta para PRONTO, nao ERRO."""
    sid = "vazia"
    session_dir = recordings_root / ".sessions" / sid
    session_dir.mkdir(parents=True)
    (session_dir / "segment_0001.wav").write_bytes(b"")  # captura nao produziu dados
    database.create_session(
        {"id": sid, "started_at": time.time(), "state": "RECORDING",
         "sample_rate": 44100, "channels": 2}
    )
    state_machine.set(State.FINALIZING, force=True)

    manager._finalize_inner(sid, interrupted=False)

    assert database.get_session(sid) is None      # nada capturado, nada salvo
    assert not session_dir.exists()               # sem lixo em disco
    assert state_machine.snapshot()["state"] == State.IDLE
