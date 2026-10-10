import pytest

from backend.session import (
    ExecutionRecoveryRollbackError as Error,
    ExecutionRecoveryRollbackService,
)


def _service(recovery_statuses, current_states, active_checkpoints):
    return ExecutionRecoveryRollbackService(
        recovery_status_resolver=recovery_statuses.get,
        current_state_resolver=lambda session_id: current_states.get(session_id, {}),
        active_checkpoint_resolver=active_checkpoints.get,
    )


class TestExecutionRecoveryRollbackService:
    def test_prepare_rollback(self):
        rollback_service = _service(
            {"session-1": "ACTIVE"}, {"session-1": {"x": 1}}, {"session-1": "checkpoint-1"}
        )

        rollback = rollback_service.prepare("session-1")

        assert rollback.session_id == "session-1"
        assert rollback.checkpoint_id == "checkpoint-1"
        assert rollback.state == {"x": 1}
        assert rollback.rollback_id
        assert rollback.created_at is not None
        assert rollback_service.status(rollback.rollback_id) == "PREPARED"

        with pytest.raises(Error):
            rollback_service.prepare("unknown-session")

    def test_execute_rollback(self):
        rollback_service = _service(
            {"session-1": "ACTIVE"}, {"session-1": {"x": 1}}, {"session-1": "checkpoint-1"}
        )
        rollback = rollback_service.prepare("session-1")

        executed = rollback_service.execute(rollback.rollback_id)

        assert executed.rollback_id == rollback.rollback_id
        assert rollback_service.status(rollback.rollback_id) == "EXECUTED"

        with pytest.raises(Error):
            rollback_service.execute(rollback.rollback_id)

    def test_state_restoration(self):
        current_states = {"session-1": {"x": 1}}
        rollback_service = _service({"session-1": "ACTIVE"}, current_states, {"session-1": "checkpoint-1"})
        rollback = rollback_service.prepare("session-1")

        with pytest.raises(Error):
            rollback_service.restore(rollback.rollback_id)

        current_states["session-1"]["x"] = 999

        rollback_service.execute(rollback.rollback_id)
        restored = rollback_service.restore(rollback.rollback_id)

        assert restored == {"x": 1}

    def test_completed_session_rejection(self):
        rollback_service = _service({"session-1": "COMPLETED"}, {}, {"session-1": "checkpoint-1"})

        with pytest.raises(Error):
            rollback_service.prepare("session-1")

    def test_atomic_failure(self):
        recovery_statuses = {"session-1": "ACTIVE"}
        rollback_service = _service(recovery_statuses, {"session-1": {"x": 1}}, {"session-1": "checkpoint-1"})
        rollback = rollback_service.prepare("session-1")

        recovery_statuses["session-1"] = "COMPLETED"

        with pytest.raises(Error):
            rollback_service.execute(rollback.rollback_id)

        assert rollback_service.status(rollback.rollback_id) == "PREPARED"

    def test_status_lookup(self):
        rollback_service = _service(
            {"session-1": "ACTIVE"}, {"session-1": {"x": 1}}, {"session-1": "checkpoint-1"}
        )
        rollback = rollback_service.prepare("session-1")

        assert rollback_service.status(rollback.rollback_id) == "PREPARED"

        rollback_service.execute(rollback.rollback_id)

        assert rollback_service.status(rollback.rollback_id) == "EXECUTED"

        with pytest.raises(Error):
            rollback_service.status("unknown-rollback")
