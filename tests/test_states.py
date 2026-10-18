import pytest

from app.states import (
    TRANSITIONS,
    InvalidTransition,
    State,
    can_transition,
    SystemState,
)


def test_every_state_is_reachable():
    for target in State.ALL:
        origins = [s for s in State.ALL if can_transition(s, target)]
        assert origins, f"estado {target} inalcançavel"


def test_no_conflicting_transitions():
    # jamais e possivel iniciar duas gravacoes
    assert not can_transition(State.RECORDING, State.RECORDING)
    # nem finalizar sem estar gravando
    assert not can_transition(State.IDLE, State.FINALIZING)
    # nem pular a consolidacao
    assert not can_transition(State.RECORDING, State.COMPLETED)


def test_recording_flow():
    assert can_transition(State.IDLE, State.RECORDING)
    assert can_transition(State.RECORDING, State.FINALIZING)
    assert can_transition(State.FINALIZING, State.UPLOADING)
    assert can_transition(State.UPLOADING, State.COMPLETED)
    assert can_transition(State.COMPLETED, State.IDLE)


def test_recovery_flow():
    assert can_transition(State.IDLE, State.RECOVERY_REQUIRED)
    assert can_transition(State.RECOVERY_REQUIRED, State.FINALIZING)
    assert can_transition(State.RECOVERY_REQUIRED, State.IDLE)
    # so pode iniciar nova gravacao depois de resolver a interrompida
    assert not can_transition(State.RECOVERY_REQUIRED, State.RECORDING)


def test_unknown_state_rejected():
    assert not can_transition(State.IDLE, "QUALQUER_COISA")


def test_invalid_transition_raises(fresh_state):
    fresh_state.set(State.IDLE, force=True)
    with pytest.raises(InvalidTransition):
        fresh_state.set(State.FINALIZING)
    assert fresh_state.state == State.IDLE


def test_set_returns_state(fresh_state):
    fresh_state.set(State.IDLE, force=True)
    assert fresh_state.set(State.RECORDING) == State.RECORDING


def test_try_set_does_not_raise(fresh_state):
    fresh_state.set(State.IDLE, force=True)
    assert fresh_state.try_set(State.FINALIZING) is False
    assert fresh_state.try_set(State.RECORDING) is True


def test_require_blocks_operation(fresh_state):
    fresh_state.set(State.IDLE, force=True)
    with pytest.raises(InvalidTransition):
        fresh_state.require(State.RECORDING)


def test_snapshot_has_source_of_truth_fields(fresh_state):
    fresh_state.set(State.RECORDING, detail="x", session_id="abc", force=True)
    snap = fresh_state.snapshot()
    assert snap["state"] == State.RECORDING
    assert snap["session_id"] == "abc"
    assert snap["detail"] == "x"
    assert snap["since"] > 0


def test_transition_table_covers_all_states():
    for state in State.ALL:
        assert state in TRANSITIONS


def test_force_allows_boot_recovery():
    st = SystemState()
    st.set(State.RECOVERY_REQUIRED, force=True)
    assert st.state == State.RECOVERY_REQUIRED
