from datetime import datetime

import pytest

from backend.agent_task_event_analytics import (
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskEventFailureRecoveryPlanner,
)
from backend.agent_task_events import (
    LIFECYCLE_TRANSITIONED,
    InMemoryAgentTaskEventStore,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventReplayService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import FAILED, PLANNED
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult
from backend.agent_task_readiness import AgentTaskReadinessCheck, AgentTaskReadinessResult
from backend.agent_task_recovery_execution_precondition_snapshots import (
    InvalidAgentTaskRecoveryExecutionPreconditionValidationError,
    LLMAgentTaskRecoveryExecutionPreconditionSnapshotService,
    LLMAgentTaskRecoveryExecutionPreconditionValidationService,
)
from backend.agent_task_recovery_guardrails import (
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightApprovalService,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightAuthorizationValidationService,
    LLMAgentTaskRecoveryPreflightFreshnessService,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightService,
    LLMAgentTaskRecoveryPreflightStore,
)


class _FakeReadinessService:
    def __init__(self, policy_passed=True, dependencies_passed=True):
        self.set(policy_passed=policy_passed, dependencies_passed=dependencies_passed)

    def set(self, policy_passed=True, dependencies_passed=True):
        checks = [
            AgentTaskReadinessCheck(name="lifecycle_state", passed=True),
            AgentTaskReadinessCheck(
                name="dependencies", passed=dependencies_passed,
                detail=None if dependencies_passed else "dependency X is not yet resolved",
            ),
            AgentTaskReadinessCheck(
                name="policy", passed=policy_passed, detail=None if policy_passed else "policy denies task execution"
            ),
        ]
        blocking = [c.detail for c in checks if not c.passed and c.detail]
        self._result = AgentTaskReadinessResult(
            ready=not blocking, task_id="unused", blocking_reasons=blocking, warnings=[], checks=checks
        )

    def check(self, task_id):
        return self._result


class _FakeRetryEligibilityService:
    def __init__(self, eligible=True, reason="eligible"):
        self.set(eligible=eligible, reason=reason)

    def set(self, eligible=True, reason="eligible"):
        self._result = RetryEligibilityResult(task_id="unused", eligible=eligible, reason=reason)

    def check(self, task_id):
        return self._result


class _FakeRetryScheduler:
    def get_retry_schedule(self, task_id):
        return None


class _FakeDeadLetterService:
    def get(self, task_id):
        return None


class _FakeReservationService:
    def is_reservation_valid(self, task_id):
        return False


def _stack():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    replay_service = LLMAgentTaskEventReplayService(query_service=query_service)

    readiness = _FakeReadinessService()
    retry_eligibility = _FakeRetryEligibilityService()

    planner = LLMAgentTaskEventFailureRecoveryPlanner(
        classifier=classifier, readiness_service=readiness, retry_eligibility_service=retry_eligibility
    )
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier, replay_service=replay_service,
        readiness_service=readiness, retry_eligibility_service=retry_eligibility,
        retry_scheduler=_FakeRetryScheduler(), dead_letter_service=_FakeDeadLetterService(),
        reservation_service=_FakeReservationService(),
    )
    evaluation_service = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)
    preflight_service = LLMAgentTaskRecoveryPreflightService(planner=planner, evaluation_service=evaluation_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    freshness_service = LLMAgentTaskRecoveryPreflightFreshnessService(
        preflight_store=preflight_store, classifier=classifier, replay_service=replay_service,
        readiness_service=readiness, retry_eligibility_service=retry_eligibility,
    )
    invalidation_service = LLMAgentTaskRecoveryPreflightInvalidationService(
        preflight_store=preflight_store, freshness_service=freshness_service
    )
    approval_service = LLMAgentTaskRecoveryPreflightApprovalService(
        preflight_store=preflight_store, invalidation_service=invalidation_service
    )
    authorization_service = LLMAgentTaskRecoveryPreflightAuthorizationService(
        preflight_store=preflight_store, approval_service=approval_service,
        invalidation_service=invalidation_service, evaluation_service=evaluation_service,
    )
    authorization_validation_service = LLMAgentTaskRecoveryPreflightAuthorizationValidationService(
        authorization_service=authorization_service, preflight_store=preflight_store,
        invalidation_service=invalidation_service, freshness_service=freshness_service,
        approval_service=approval_service, evaluation_service=evaluation_service,
    )
    snapshot_service = LLMAgentTaskRecoveryExecutionPreconditionSnapshotService(
        authorization_service=authorization_service, preflight_store=preflight_store,
        retry_eligibility_service=retry_eligibility, readiness_service=readiness,
    )
    validation_service = LLMAgentTaskRecoveryExecutionPreconditionValidationService(
        snapshot_service=snapshot_service, guard_service=guard,
        authorization_validation_service=authorization_validation_service,
    )
    return {
        "event_service": event_service,
        "readiness": readiness,
        "retry_eligibility": retry_eligibility,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "snapshot_service": snapshot_service,
        "validation_service": validation_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _snapshot(s, task_id="task-1"):
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    authorization = s["authorization_service"].authorize(task_id, preflight.preflight_id)
    snapshot = s["snapshot_service"].capture(task_id, authorization.authorization_id)
    return preflight, authorization, snapshot


def test_successful_validation_of_unchanged_state():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization, snapshot = _snapshot(s)

    result = s["validation_service"].validate("task-1", snapshot.snapshot_id)

    assert result.valid is True
    assert result.blocking_reasons == ()
    assert result.authorization_id == authorization.authorization_id
    assert result.diff.changed is False
    assert isinstance(result.validated_at, datetime)
    assert s["validation_service"].is_valid("task-1", snapshot.snapshot_id) is True


def test_validate_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionValidationError):
        s["validation_service"].validate("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionValidationError):
        s["validation_service"].validate("task-1", "")


def test_validate_rejects_unknown_snapshot():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionValidationError):
        s["validation_service"].validate("task-1", "never-existed")


def test_revoked_authorization_is_execution_blocking():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization, snapshot = _snapshot(s)

    s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="operator revoked")

    result = s["validation_service"].validate("task-1", snapshot.snapshot_id)

    assert result.valid is False
    assert any("revoked" in reason for reason in result.blocking_reasons)
    assert s["validation_service"].is_valid("task-1", snapshot.snapshot_id) is False


def test_newly_blocked_dependency_is_execution_blocking():
    s = _stack()
    _fail_task(s["event_service"])
    _, _, snapshot = _snapshot(s)

    s["readiness"].set(dependencies_passed=False)

    result = s["validation_service"].validate("task-1", snapshot.snapshot_id)

    assert result.valid is False
    assert result.guard_result is not None
    assert any("dependenc" in reason for reason in result.blocking_reasons)
    assert result.diff.changed is True


def test_retry_budget_exhaustion_is_execution_blocking():
    s = _stack()
    _fail_task(s["event_service"])
    _, _, snapshot = _snapshot(s)

    s["retry_eligibility"].set(eligible=False, reason="max attempts exhausted")

    result = s["validation_service"].validate("task-1", snapshot.snapshot_id)

    assert result.valid is False
    assert any("not currently eligible" in reason for reason in result.blocking_reasons)


def test_superseded_preflight_evidence_is_execution_blocking():
    s = _stack()
    _fail_task(s["event_service"])
    _, _, snapshot = _snapshot(s)

    # A newer preflight (genuinely different content, so it isn't deduped
    # as the same one) becomes task-1's own current preflight -- the
    # snapshot's authorization now points at stale, superseded evidence.
    s["readiness"].set(dependencies_passed=False)
    s["preflight_store"].save(s["preflight_service"].run("task-1"))

    result = s["validation_service"].validate("task-1", snapshot.snapshot_id)

    assert result.valid is False
    assert any("superseded" in reason for reason in result.blocking_reasons)


def test_diff_can_report_harmless_change_without_blocking():
    s = _stack()
    _fail_task(s["event_service"])
    _, _, snapshot = _snapshot(s)

    # Still eligible, only the human-readable reason changed -- observed by
    # compare()'s diff, but never itself blocking (eligible stays True).
    s["retry_eligibility"].set(eligible=True, reason="re-confirmed eligible")

    result = s["validation_service"].validate("task-1", snapshot.snapshot_id)

    assert result.diff.retry_eligibility_changed is True
    assert result.diff.changed is True
    assert result.valid is True
    assert result.blocking_reasons == ()
