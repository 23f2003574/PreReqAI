import pytest

from backend.session import (
    ExecutionRecoveryCheckpoint,
    ExecutionRecoveryConflictError as Error,
    ExecutionRecoveryConflictService,
)


def _service(checkpoints, current_states):
    checkpoints_by_id = {checkpoint.checkpoint_id: checkpoint for checkpoint in checkpoints}

    return ExecutionRecoveryConflictService(
        checkpoint_resolver=checkpoints_by_id.get,
        current_state_resolver=lambda session_id: current_states.get(session_id, {}),
    )


class TestExecutionRecoveryConflictService:
    def test_detect_conflict(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"step": 5})
        conflict_service = _service([checkpoint], {"session-1": {"step": 3}})

        conflicts = conflict_service.detect("session-1", checkpoint.checkpoint_id)

        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict.session_id == "session-1"
        assert conflict.checkpoint_id == checkpoint.checkpoint_id
        assert conflict.field == "step"
        assert conflict.checkpoint_value == 5
        assert conflict.current_value == 3

    def test_no_conflict_state(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"step": 5})
        conflict_service = _service([checkpoint], {"session-1": {"step": 5}})

        conflicts = conflict_service.detect("session-1", checkpoint.checkpoint_id)

        assert conflicts == ()
        assert conflict_service.conflicts("session-1") == ()

        conflict_service.clear("session-1")

    def test_multiple_conflicts(self):
        checkpoint = ExecutionRecoveryCheckpoint(
            session_id="session-1", stage_id="stage-1", state={"a": 1, "b": 2, "c": 3}
        )
        conflict_service = _service([checkpoint], {"session-1": {"a": 9, "b": 2, "c": 8}})

        conflicts = conflict_service.detect("session-1", checkpoint.checkpoint_id)

        assert [conflict.field for conflict in conflicts] == ["a", "c"]

    def test_resolve_conflict(self):
        checkpoint = ExecutionRecoveryCheckpoint(
            session_id="session-1", stage_id="stage-1", state={"a": 1, "b": 2}
        )
        conflict_service = _service([checkpoint], {"session-1": {"a": 9, "b": 8}})
        conflicts = conflict_service.detect("session-1", checkpoint.checkpoint_id)
        first, second = conflicts

        resolved = conflict_service.resolve(first.conflict_id, "USE_CHECKPOINT")

        assert resolved == first
        assert conflict_service.conflicts("session-1") == (second,)

        with pytest.raises(Error):
            conflict_service.resolve(first.conflict_id, "USE_CHECKPOINT")

        with pytest.raises(Error):
            conflict_service.resolve("unknown-conflict", "USE_CHECKPOINT")

        with pytest.raises(Error):
            conflict_service.resolve(second.conflict_id, None)

    def test_unresolved_conflict_blocks_recovery(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"step": 5})
        conflict_service = _service([checkpoint], {"session-1": {"step": 3}})
        conflicts = conflict_service.detect("session-1", checkpoint.checkpoint_id)

        with pytest.raises(Error):
            conflict_service.clear("session-1")

        conflict_service.resolve(conflicts[0].conflict_id, "USE_CURRENT")

        conflict_service.clear("session-1")
        assert conflict_service.conflicts("session-1") == ()

    def test_clear_resolved_conflicts(self):
        checkpoint = ExecutionRecoveryCheckpoint(
            session_id="session-1", stage_id="stage-1", state={"a": 1, "b": 2}
        )
        conflict_service = _service([checkpoint], {"session-1": {"a": 9, "b": 8}})
        conflicts = conflict_service.detect("session-1", checkpoint.checkpoint_id)

        for conflict in conflicts:
            conflict_service.resolve(conflict.conflict_id, "USE_CHECKPOINT")

        conflict_service.clear("session-1")

        with pytest.raises(Error):
            conflict_service.resolve(conflicts[0].conflict_id, "USE_CHECKPOINT")

        redetected = conflict_service.detect("session-1", checkpoint.checkpoint_id)
        assert len(redetected) == 2
