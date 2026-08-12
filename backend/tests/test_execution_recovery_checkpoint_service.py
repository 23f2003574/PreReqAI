from types import MappingProxyType

import pytest

from backend.session import (
    ExecutionRecoveryCheckpointError as Error,
    ExecutionRecoveryCheckpointService,
)


def _resolver(statuses):
    return lambda session_id: statuses.get(session_id)


class TestExecutionRecoveryCheckpointService:
    def test_create_checkpoint(self):
        checkpoint_service = ExecutionRecoveryCheckpointService(_resolver({}))

        checkpoint = checkpoint_service.create("session-1", "stage-1", {"step": 3})

        assert checkpoint.session_id == "session-1"
        assert checkpoint.stage_id == "stage-1"
        assert checkpoint.state == {"step": 3}
        assert checkpoint.checkpoint_id
        assert checkpoint.created_at is not None

    def test_latest_lookup(self):
        checkpoint_service = ExecutionRecoveryCheckpointService(_resolver({}))
        checkpoint_service.create("session-1", "stage-1", {"step": 1})
        second = checkpoint_service.create("session-1", "stage-1", {"step": 2})

        assert checkpoint_service.latest("session-1") == {"stage-1": second}

        with pytest.raises(Error):
            checkpoint_service.latest("")

    def test_restore(self):
        checkpoint_service = ExecutionRecoveryCheckpointService(_resolver({"session-1": "INTERRUPTED"}))
        checkpoint = checkpoint_service.create("session-1", "stage-1", {"step": 1})

        restored = checkpoint_service.restore(checkpoint.checkpoint_id)

        assert restored == checkpoint

        checkpoint_service.delete(checkpoint.checkpoint_id)

        with pytest.raises(Error):
            checkpoint_service.restore(checkpoint.checkpoint_id)

    def test_stage_isolation(self):
        checkpoint_service = ExecutionRecoveryCheckpointService(_resolver({}))
        first = checkpoint_service.create("session-1", "stage-1", {"step": 1})
        second = checkpoint_service.create("session-1", "stage-2", {"step": 1})

        assert checkpoint_service.latest("session-1") == {"stage-1": first, "stage-2": second}

        updated_first = checkpoint_service.create("session-1", "stage-1", {"step": 2})

        latest = checkpoint_service.latest("session-1")
        assert latest == {"stage-1": updated_first, "stage-2": second}

    def test_immutable_state(self):
        checkpoint_service = ExecutionRecoveryCheckpointService(_resolver({}))
        state = {"step": 1}

        checkpoint = checkpoint_service.create("session-1", "stage-1", state)

        assert isinstance(checkpoint.state, MappingProxyType)

        with pytest.raises(TypeError):
            checkpoint.state["step"] = 2

        state["step"] = 999
        assert checkpoint.state["step"] == 1

        with pytest.raises(AttributeError):
            checkpoint.state = {"step": 2}

    def test_invalid_restore(self):
        checkpoint_service = ExecutionRecoveryCheckpointService(_resolver({"session-1": "ACTIVE"}))
        checkpoint = checkpoint_service.create("session-1", "stage-1", {"step": 1})

        with pytest.raises(Error):
            checkpoint_service.restore("unknown-checkpoint")

        with pytest.raises(Error):
            checkpoint_service.restore(checkpoint.checkpoint_id)

        unknown_session_service = ExecutionRecoveryCheckpointService(_resolver({}))
        orphan = unknown_session_service.create("session-2", "stage-1", {"step": 1})

        with pytest.raises(Error):
            unknown_session_service.restore(orphan.checkpoint_id)
