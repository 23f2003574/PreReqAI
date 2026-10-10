import pytest

from backend.session import (
    ExecutionRecoveryCheckpoint,
    ExecutionRecoveryValidationError as Error,
    ExecutionRecoveryValidationService,
)


def _service(checkpoints, statuses, stages):
    checkpoints_by_id = {checkpoint.checkpoint_id: checkpoint for checkpoint in checkpoints}

    def checkpoints_by_session(session_id):
        return {
            checkpoint.stage_id: checkpoint for checkpoint in checkpoints if checkpoint.session_id == session_id
        }

    return ExecutionRecoveryValidationService(
        checkpoint_resolver=checkpoints_by_id.get,
        session_checkpoints_resolver=checkpoints_by_session,
        session_status_resolver=statuses.get,
        session_stage_resolver=stages.get,
    )


class TestExecutionRecoveryValidationService:
    def test_valid_checkpoint(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"step": 1})
        service = _service([checkpoint], {"session-1": "INTERRUPTED"}, {"session-1": frozenset({"stage-1"})})

        validation = service.validate(checkpoint.checkpoint_id)

        assert validation.checkpoint_id == checkpoint.checkpoint_id
        assert validation.valid is True
        assert validation.violations == ()

    def test_incomplete_checkpoint(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={})
        service = _service([checkpoint], {"session-1": "INTERRUPTED"}, {"session-1": frozenset({"stage-1"})})

        validation = service.validate(checkpoint.checkpoint_id)

        assert validation.valid is False
        assert any("state" in violation for violation in validation.violations)

    def test_completed_session_rejection(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"step": 1})
        service = _service([checkpoint], {"session-1": "COMPLETED"}, {"session-1": frozenset({"stage-1"})})

        validation = service.validate(checkpoint.checkpoint_id)

        assert validation.valid is False
        assert any("COMPLETED" in violation for violation in validation.violations)

    def test_invalid_stage(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-99", state={"step": 1})
        service = _service([checkpoint], {"session-1": "INTERRUPTED"}, {"session-1": frozenset({"stage-1"})})

        validation = service.validate(checkpoint.checkpoint_id)

        assert validation.valid is False
        assert any("stage" in violation.lower() for violation in validation.violations)

        with pytest.raises(Error):
            service.validate("unknown-checkpoint")

    def test_validation_report(self):
        good = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"step": 1})
        bad = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-2", state={})
        service = _service(
            [good, bad],
            {"session-1": "INTERRUPTED"},
            {"session-1": frozenset({"stage-1", "stage-2"})},
        )

        report = service.report("session-1")

        assert report["session_id"] == "session-1"
        assert report["total"] == 2
        assert report["valid_count"] == 1
        assert report["invalid_count"] == 1
        assert [validation.checkpoint_id for validation in report["validations"]] == [
            good.checkpoint_id,
            bad.checkpoint_id,
        ]

        invalid = service.invalid("session-1")

        assert len(invalid) == 1
        assert invalid[0].checkpoint_id == bad.checkpoint_id
