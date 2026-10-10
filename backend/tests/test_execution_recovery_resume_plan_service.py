import pytest

from backend.session import (
    ExecutionRecoveryCheckpoint,
    ExecutionRecoveryResumePlanError as Error,
    ExecutionRecoveryResumePlanService,
)


def _service(checkpoints, valid_checkpoint_ids):
    checkpoints_by_id = {checkpoint.checkpoint_id: checkpoint for checkpoint in checkpoints}

    return ExecutionRecoveryResumePlanService(
        checkpoint_resolver=checkpoints_by_id.get,
        checkpoint_validation_resolver=lambda checkpoint_id: checkpoint_id in valid_checkpoint_ids,
    )


class TestExecutionRecoveryResumePlanService:
    def test_create_plan(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        service = _service([checkpoint], {checkpoint.checkpoint_id})

        plan = service.create("session-1", checkpoint.checkpoint_id)

        assert plan.session_id == "session-1"
        assert plan.checkpoint_id == checkpoint.checkpoint_id
        assert plan.stage_id == "stage-1"
        assert plan.plan_id
        assert plan.created_at is not None

    def test_resolve_plan(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        service = _service([checkpoint], {checkpoint.checkpoint_id})

        assert service.resolve("session-1") is None

        plan = service.create("session-1", checkpoint.checkpoint_id)

        assert service.resolve("session-1") == plan
        assert service.resolve("unknown-session") is None

    def test_update_checkpoint(self):
        first = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        second = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-2", state={"x": 2})
        service = _service([first, second], {first.checkpoint_id, second.checkpoint_id})
        plan = service.create("session-1", first.checkpoint_id)

        updated = service.update(plan.plan_id, second.checkpoint_id)

        assert updated.plan_id == plan.plan_id
        assert updated.checkpoint_id == second.checkpoint_id
        assert updated.stage_id == "stage-2"
        assert service.resolve("session-1") == updated

    def test_cancel_plan(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        service = _service([checkpoint], {checkpoint.checkpoint_id})
        plan = service.create("session-1", checkpoint.checkpoint_id)

        service.cancel(plan.plan_id)

        assert service.resolve("session-1") is None

        with pytest.raises(Error):
            service.update(plan.plan_id, checkpoint.checkpoint_id)

        with pytest.raises(Error):
            service.cancel(plan.plan_id)

    def test_duplicate_plan_rejection(self):
        first = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        second = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-2", state={"x": 2})
        service = _service([first, second], {first.checkpoint_id, second.checkpoint_id})
        plan = service.create("session-1", first.checkpoint_id)

        with pytest.raises(Error):
            service.create("session-1", second.checkpoint_id)

        service.cancel(plan.plan_id)

        recreated = service.create("session-1", second.checkpoint_id)
        assert recreated.checkpoint_id == second.checkpoint_id

    def test_invalid_checkpoint(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        service = _service([checkpoint], set())

        with pytest.raises(Error):
            service.create("session-1", checkpoint.checkpoint_id)

        with pytest.raises(Error):
            service.create("session-1", "unknown-checkpoint")

        valid_service = _service([checkpoint], {checkpoint.checkpoint_id})
        plan = valid_service.create("session-1", checkpoint.checkpoint_id)

        with pytest.raises(Error):
            valid_service.update(plan.plan_id, "unknown-checkpoint")

        with pytest.raises(Error):
            valid_service.update("unknown-plan", checkpoint.checkpoint_id)
