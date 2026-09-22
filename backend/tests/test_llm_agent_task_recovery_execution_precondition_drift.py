from datetime import datetime, timezone

import pytest

from backend.agent_task_lifecycle import COMPLETED, FAILED, PLANNED
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult
from backend.agent_task_readiness import AgentTaskReadinessCheck, AgentTaskReadinessResult
from backend.agent_task_recovery_execution_precondition_snapshots import (
    DRIFT_EXECUTION_BLOCKED,
    DRIFT_NON_BLOCKING,
    DRIFT_NONE,
    DRIFT_REQUIRES_REVALIDATION,
    AgentTaskRecoveryExecutionPreconditionFieldChange,
    AgentTaskRecoveryExecutionPreconditionSnapshotDiff,
    AgentTaskRecoveryExecutionPreconditionValidationResult,
    InvalidAgentTaskRecoveryExecutionPreconditionDriftError,
    LLMAgentTaskRecoveryExecutionPreconditionDriftService,
)
from backend.agent_task_recovery_guardrails import ACTIVE, REVOKED

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
TASK_ID = "task-1"
SNAPSHOT_ID = "snapshot-1"
AUTH_ID = "auth-1"
PREFLIGHT_ID = "preflight-1"

_READY = AgentTaskReadinessResult(
    ready=True, task_id=TASK_ID, blocking_reasons=[], warnings=[],
    checks=[AgentTaskReadinessCheck(name="dependencies", passed=True)],
)
_NOT_READY = AgentTaskReadinessResult(
    ready=False, task_id=TASK_ID, blocking_reasons=["dependency X is not yet resolved"], warnings=[],
    checks=[AgentTaskReadinessCheck(name="dependencies", passed=False, detail="dependency X is not yet resolved")],
)
_ELIGIBLE = RetryEligibilityResult(task_id=TASK_ID, eligible=True, reason="eligible")


def _diff(changes=(), current_authorization_status=ACTIVE, current_task_state=FAILED,
          current_retry_eligibility=None, current_readiness=None):
    changes = tuple(changes)
    fields = {change.field for change in changes}
    return AgentTaskRecoveryExecutionPreconditionSnapshotDiff(
        task_id=TASK_ID, snapshot_id=SNAPSHOT_ID, authorization_id=AUTH_ID, preflight_id=PREFLIGHT_ID,
        changed=bool(changes),
        authorization_status_changed="authorization_status" in fields,
        task_state_changed="task_state" in fields,
        retry_eligibility_changed="retry_eligibility" in fields,
        readiness_changed="readiness" in fields,
        changes=changes,
        current_authorization_status=current_authorization_status,
        current_task_state=current_task_state,
        current_retry_eligibility=current_retry_eligibility,
        current_readiness=current_readiness,
        compared_at=NOW,
    )


def _validation(diff, valid=True, blocking_reasons=(), warnings=()):
    return AgentTaskRecoveryExecutionPreconditionValidationResult(
        task_id=TASK_ID, snapshot_id=SNAPSHOT_ID, authorization_id=AUTH_ID, preflight_id=PREFLIGHT_ID,
        valid=valid, blocking_reasons=tuple(blocking_reasons), warnings=tuple(warnings),
        diff=diff, authorization_validation=None, guard_result=None, validated_at=NOW,
    )


class _FakeValidationService:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def validate(self, task_id, snapshot_id):
        if self._error is not None:
            raise self._error
        assert task_id == TASK_ID and snapshot_id == SNAPSHOT_ID
        return self._result


def _classify(result=None, error=None):
    service = LLMAgentTaskRecoveryExecutionPreconditionDriftService(
        validation_service=_FakeValidationService(result=result, error=error)
    )
    return service.classify(TASK_ID, SNAPSHOT_ID)


def test_unchanged_state_classifies_as_none():
    result = _classify(_validation(_diff(), valid=True))

    assert result.category == DRIFT_NONE
    assert result.items == ()
    assert result.execution_may_continue is True


def test_validate_rejects_blank_arguments():
    service = LLMAgentTaskRecoveryExecutionPreconditionDriftService(validation_service=_FakeValidationService())
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDriftError):
        service.classify("", SNAPSHOT_ID)
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDriftError):
        service.classify(TASK_ID, "")


def test_unknown_snapshot_propagates_as_drift_error():
    from backend.agent_task_recovery_execution_precondition_snapshots import (
        InvalidAgentTaskRecoveryExecutionPreconditionValidationError,
    )

    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDriftError):
        _classify(error=InvalidAgentTaskRecoveryExecutionPreconditionValidationError("no such snapshot"))


def test_harmless_retry_reason_change_is_non_blocking():
    changed_retry = RetryEligibilityResult(task_id=TASK_ID, eligible=True, reason="re-confirmed eligible")
    change = AgentTaskRecoveryExecutionPreconditionFieldChange("retry_eligibility", _ELIGIBLE, changed_retry)
    diff = _diff(changes=[change], current_retry_eligibility=changed_retry)

    result = _classify(_validation(diff, valid=True))

    assert result.category == DRIFT_NON_BLOCKING
    assert result.execution_may_continue is True
    (item,) = result.items
    assert item.concern == "retry_budget"
    assert item.execution_may_continue is True


def test_revoked_authorization_is_execution_blocked():
    change = AgentTaskRecoveryExecutionPreconditionFieldChange("authorization_status", ACTIVE, REVOKED)
    diff = _diff(changes=[change], current_authorization_status=REVOKED)

    result = _classify(_validation(diff, valid=False, blocking_reasons=("authorization has been revoked: test",)))

    assert result.category == DRIFT_EXECUTION_BLOCKED
    assert result.execution_may_continue is False
    (item,) = result.items
    assert item.concern == "authorization"
    assert item.execution_may_continue is False


def test_authorization_status_flap_while_still_active_requires_revalidation():
    change = AgentTaskRecoveryExecutionPreconditionFieldChange("authorization_status", ACTIVE, ACTIVE)
    diff = _diff(changes=[change], current_authorization_status=ACTIVE)

    result = _classify(_validation(diff, valid=True))

    assert result.category == DRIFT_REQUIRES_REVALIDATION
    assert result.execution_may_continue is True
    (item,) = result.items
    assert item.execution_may_continue is True


def test_task_reaching_completed_is_execution_blocked():
    change = AgentTaskRecoveryExecutionPreconditionFieldChange("task_state", FAILED, COMPLETED)
    diff = _diff(changes=[change], current_task_state=COMPLETED)

    result = _classify(_validation(diff, valid=False, blocking_reasons=("task has already completed",)))

    assert result.category == DRIFT_EXECUTION_BLOCKED
    (item,) = result.items
    assert item.concern == "task_eligibility"


def test_task_state_moved_between_live_states_requires_revalidation():
    change = AgentTaskRecoveryExecutionPreconditionFieldChange("task_state", FAILED, PLANNED)
    diff = _diff(changes=[change], current_task_state=PLANNED)

    result = _classify(_validation(diff, valid=True))

    assert result.category == DRIFT_REQUIRES_REVALIDATION
    assert result.execution_may_continue is True


def test_newly_blocked_dependency_is_execution_blocked():
    change = AgentTaskRecoveryExecutionPreconditionFieldChange("readiness", _READY, _NOT_READY)
    diff = _diff(changes=[change], current_readiness=_NOT_READY)

    result = _classify(
        _validation(diff, valid=False, blocking_reasons=("requires resolved dependencies: dependency X",))
    )

    assert result.category == DRIFT_EXECUTION_BLOCKED
    (item,) = result.items
    assert item.concern == "dependency_and_policy_readiness"


def test_retry_budget_exhaustion_is_execution_blocked():
    exhausted = RetryEligibilityResult(task_id=TASK_ID, eligible=False, reason="max attempts exhausted")
    change = AgentTaskRecoveryExecutionPreconditionFieldChange("retry_eligibility", _ELIGIBLE, exhausted)
    diff = _diff(changes=[change], current_retry_eligibility=exhausted)

    result = _classify(_validation(diff, valid=False, blocking_reasons=("retry is not currently eligible",)))

    assert result.category == DRIFT_EXECUTION_BLOCKED
    (item,) = result.items
    assert item.concern == "retry_budget"


def test_ambiguous_retry_eligibility_becoming_unreadable_requires_revalidation():
    change = AgentTaskRecoveryExecutionPreconditionFieldChange("retry_eligibility", _ELIGIBLE, None)
    diff = _diff(changes=[change], current_retry_eligibility=None)

    result = _classify(_validation(diff, valid=True))

    assert result.category == DRIFT_REQUIRES_REVALIDATION
    assert result.execution_may_continue is True
    (item,) = result.items
    assert "cannot be safely compared" in item.reason


def test_ambiguous_readiness_becoming_unreadable_requires_revalidation():
    change = AgentTaskRecoveryExecutionPreconditionFieldChange("readiness", _READY, None)
    diff = _diff(changes=[change], current_readiness=None)

    result = _classify(_validation(diff, valid=True))

    assert result.category == DRIFT_REQUIRES_REVALIDATION


def test_blocking_reason_not_explained_by_any_field_fails_closed():
    diff = _diff()  # nothing tracked changed at all

    result = _classify(
        _validation(diff, valid=False, blocking_reasons=("the referenced preflight has no recovery plan",))
    )

    assert result.category == DRIFT_EXECUTION_BLOCKED
    assert result.execution_may_continue is False
    (item,) = result.items
    assert item.field is None
    assert item.concern == "unclassified"
    assert "no recovery plan" in item.reason


def test_severity_is_the_worst_among_multiple_items():
    revoked = AgentTaskRecoveryExecutionPreconditionFieldChange("authorization_status", ACTIVE, REVOKED)
    harmless_retry = AgentTaskRecoveryExecutionPreconditionFieldChange(
        "retry_eligibility", _ELIGIBLE, RetryEligibilityResult(task_id=TASK_ID, eligible=True, reason="still fine")
    )
    diff = _diff(
        changes=[revoked, harmless_retry], current_authorization_status=REVOKED,
        current_retry_eligibility=RetryEligibilityResult(task_id=TASK_ID, eligible=True, reason="still fine"),
    )

    result = _classify(_validation(diff, valid=False, blocking_reasons=("authorization has been revoked",)))

    assert result.category == DRIFT_EXECUTION_BLOCKED
    assert len(result.items) == 2
