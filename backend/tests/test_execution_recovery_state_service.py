from types import MappingProxyType

import pytest

from backend.session import (
    ExecutionRecoveryCheckpoint,
    ExecutionRecoveryStateError as Error,
    ExecutionRecoveryStateService,
)


def _service(checkpoints, valid_checkpoint_ids, statuses):
    checkpoints_by_id = {checkpoint.checkpoint_id: checkpoint for checkpoint in checkpoints}

    return ExecutionRecoveryStateService(
        checkpoint_resolver=checkpoints_by_id.get,
        checkpoint_validation_resolver=lambda checkpoint_id: checkpoint_id in valid_checkpoint_ids,
        session_status_resolver=statuses.get,
    )


class TestExecutionRecoveryStateService:
    def test_reconstruct_state(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        service = _service([checkpoint], {checkpoint.checkpoint_id}, {})

        state = service.reconstruct(checkpoint.checkpoint_id)

        assert state.session_id == "session-1"
        assert state.checkpoint_id == checkpoint.checkpoint_id
        assert state.stage_id == "stage-1"
        assert state.variables == {"x": 1}
        assert isinstance(state.variables, MappingProxyType)
        assert state.restored_at is not None

    def test_state_lookup(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        service = _service([checkpoint], {checkpoint.checkpoint_id}, {})

        assert service.state("session-1") is None

        reconstructed = service.reconstruct(checkpoint.checkpoint_id)

        assert service.state("session-1") == reconstructed

    def test_apply_state(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        service = _service([checkpoint], {checkpoint.checkpoint_id}, {"session-1": "INTERRUPTED"})
        service.reconstruct(checkpoint.checkpoint_id)

        applied = service.apply("session-1")

        assert applied.session_id == "session-1"
        assert service.state("session-1") is None

        with pytest.raises(Error):
            service.apply("session-1")

    def test_active_session_protection(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        service = _service([checkpoint], {checkpoint.checkpoint_id}, {"session-1": "ACTIVE"})
        service.reconstruct(checkpoint.checkpoint_id)

        with pytest.raises(Error):
            service.apply("session-1")

        assert service.state("session-1") is not None

    def test_clear_state(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        service = _service([checkpoint], {checkpoint.checkpoint_id}, {})
        service.reconstruct(checkpoint.checkpoint_id)

        service.clear("session-1")

        assert service.state("session-1") is None

        service.clear("session-1")

    def test_invalid_checkpoint_rejection(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        service = _service([checkpoint], set(), {})

        with pytest.raises(Error):
            service.reconstruct(checkpoint.checkpoint_id)

        with pytest.raises(Error):
            service.reconstruct("unknown-checkpoint")
