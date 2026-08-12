import pytest

from backend.session import (
    ExecutionRecoveryCheckpoint,
    ExecutionRecoveryGateError as Error,
    ExecutionRecoveryGateService,
)


def _service(checkpoints, valid_checkpoint_ids, conflicts_by_session):
    checkpoints_by_id = {checkpoint.checkpoint_id: checkpoint for checkpoint in checkpoints}

    return ExecutionRecoveryGateService(
        checkpoint_resolver=checkpoints_by_id.get,
        checkpoint_validation_resolver=lambda checkpoint_id: checkpoint_id in valid_checkpoint_ids,
        conflicts_resolver=lambda session_id: conflicts_by_session.get(session_id, ()),
    )


class TestExecutionRecoveryGateService:
    def test_create_evaluate_gate(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        gate_service = _service([checkpoint], {checkpoint.checkpoint_id}, {})

        gate = gate_service.create("session-1", checkpoint.checkpoint_id)

        assert gate.session_id == "session-1"
        assert gate.checkpoint_id == checkpoint.checkpoint_id
        assert gate.status == "PENDING"
        assert gate.checks == ()

        evaluated = gate_service.evaluate(gate.gate_id)

        assert evaluated.gate_id == gate.gate_id
        assert len(evaluated.checks) == 3

    def test_all_checks_pass(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        gate_service = _service([checkpoint], {checkpoint.checkpoint_id}, {})
        gate = gate_service.create("session-1", checkpoint.checkpoint_id)

        evaluated = gate_service.evaluate(gate.gate_id)

        assert evaluated.status == "OPEN"
        assert gate_service.open(gate.gate_id) is True
        assert gate_service.failed(gate.gate_id) == ()

    def test_failed_check_blocks_recovery(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        gate_service = _service([checkpoint], set(), {"session-1": ["conflict-1"]})
        gate = gate_service.create("session-1", checkpoint.checkpoint_id)

        evaluated = gate_service.evaluate(gate.gate_id)

        assert evaluated.status == "BLOCKED"
        assert gate_service.open(gate.gate_id) is False

        failed = gate_service.failed(gate.gate_id)
        assert {check["name"] for check in failed} == {"validation", "conflict"}

    def test_re_evaluation(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        valid_checkpoint_ids = set()
        conflicts_by_session = {"session-1": ["conflict-1"]}
        gate_service = _service([checkpoint], valid_checkpoint_ids, conflicts_by_session)
        gate = gate_service.create("session-1", checkpoint.checkpoint_id)

        first_evaluation = gate_service.evaluate(gate.gate_id)
        assert first_evaluation.status == "BLOCKED"

        valid_checkpoint_ids.add(checkpoint.checkpoint_id)
        conflicts_by_session["session-1"] = ()

        second_evaluation = gate_service.evaluate(gate.gate_id)
        assert second_evaluation.status == "OPEN"
        assert gate_service.open(gate.gate_id) is True

    def test_failure_reasons(self):
        checkpoint = ExecutionRecoveryCheckpoint(session_id="session-1", stage_id="stage-1", state={"x": 1})
        gate_service = _service([], set(), {"session-1": ["conflict-1"]})
        gate = gate_service.create("session-1", checkpoint.checkpoint_id)

        gate_service.evaluate(gate.gate_id)
        failed = {check["name"]: check["reason"] for check in gate_service.failed(gate.gate_id)}

        assert set(failed) == {"checkpoint", "validation", "conflict"}
        assert all(reason for reason in failed.values())
        assert checkpoint.checkpoint_id in failed["checkpoint"]

    def test_unknown_gate_rejection(self):
        gate_service = _service([], set(), {})

        with pytest.raises(Error):
            gate_service.evaluate("unknown-gate")

        with pytest.raises(Error):
            gate_service.failed("unknown-gate")

        with pytest.raises(Error):
            gate_service.open("unknown-gate")
