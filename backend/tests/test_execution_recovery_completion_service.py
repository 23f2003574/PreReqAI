from datetime import datetime, timezone

import pytest

from backend.session import (
    ExecutionRecoveryAttempt,
    ExecutionRecoveryCompletionService,
    ExecutionRecoveryGate,
    ExecutionRecoveryResultError as Error,
)


def _gate(status, checkpoint_id="checkpoint-1", session_id="session-1"):
    if status == "OPEN":
        checks = ({"name": "validation", "passed": True, "reason": None},)
    else:
        checks = ({"name": "validation", "passed": False, "reason": "not valid"},)

    return ExecutionRecoveryGate(session_id=session_id, checkpoint_id=checkpoint_id, checks=checks, status=status)


def _attempt(status, attempt_number=1, plan_id="plan-1"):
    started_at = datetime.now(timezone.utc)
    finished_at = None if status == "IN_PROGRESS" else started_at
    return ExecutionRecoveryAttempt(
        plan_id=plan_id,
        attempt_number=attempt_number,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
    )


def _service(gates_by_session, conflicts_by_session, attempts_by_session):
    return ExecutionRecoveryCompletionService(
        gate_resolver=gates_by_session.get,
        unresolved_conflicts_resolver=lambda session_id: conflicts_by_session.get(session_id, ()),
        latest_attempt_resolver=attempts_by_session.get,
    )


class TestExecutionRecoveryCompletionService:
    def test_successful_completion(self):
        completion_service = _service(
            {"session-1": _gate("OPEN")}, {}, {"session-1": _attempt("SUCCEEDED")}
        )

        result = completion_service.complete("session-1")

        assert result.session_id == "session-1"
        assert result.checkpoint_id == "checkpoint-1"
        assert result.status == "COMPLETED"
        assert result.attempts == 1
        assert result.completed_at is not None
        assert result.failure_reason is None
        assert completion_service.status("session-1") == "COMPLETED"
        assert completion_service.failed("session-1") is None

    def test_gate_failure(self):
        completion_service = _service({"session-1": _gate("BLOCKED")}, {}, {})

        result = completion_service.complete("session-1")

        assert result.status == "FAILED"
        assert result.completed_at is None
        assert "OPEN" in result.failure_reason
        assert completion_service.failed("session-1") == result.failure_reason

        with pytest.raises(Error):
            completion_service.complete("unknown-session")

    def test_unresolved_conflict(self):
        completion_service = _service(
            {"session-1": _gate("OPEN")}, {"session-1": ["conflict-1"]}, {"session-1": _attempt("SUCCEEDED")}
        )

        result = completion_service.complete("session-1")

        assert result.status == "FAILED"
        assert "conflict" in result.failure_reason.lower()

    def test_failed_attempt(self):
        completion_service = _service(
            {"session-1": _gate("OPEN")}, {}, {"session-1": _attempt("FAILED")}
        )

        result = completion_service.complete("session-1")

        assert result.status == "FAILED"
        assert result.attempts == 1
        assert "attempt" in result.failure_reason.lower()

        no_attempt_service = _service({"session-1": _gate("OPEN")}, {}, {})
        no_attempt_result = no_attempt_service.complete("session-1")

        assert no_attempt_result.status == "FAILED"
        assert no_attempt_result.attempts == 0

    def test_terminal_completion(self):
        completion_service = _service(
            {"session-1": _gate("OPEN")}, {}, {"session-1": _attempt("SUCCEEDED")}
        )
        completion_service.complete("session-1")

        with pytest.raises(Error):
            completion_service.complete("session-1")

        with pytest.raises(Error):
            completion_service.reset("session-1")

    def test_reset_failed_recovery(self):
        gates_by_session = {"session-1": _gate("BLOCKED")}
        attempts_by_session = {}
        completion_service = _service(gates_by_session, {}, attempts_by_session)

        failed_result = completion_service.complete("session-1")
        assert failed_result.status == "FAILED"

        completion_service.reset("session-1")

        with pytest.raises(Error):
            completion_service.status("session-1")

        with pytest.raises(Error):
            completion_service.reset("session-1")

        gates_by_session["session-1"] = _gate("OPEN")
        attempts_by_session["session-1"] = _attempt("SUCCEEDED")

        retried_result = completion_service.complete("session-1")
        assert retried_result.status == "COMPLETED"
