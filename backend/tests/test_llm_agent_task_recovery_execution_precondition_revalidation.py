from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_RETRY,
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
    DRIFT_EXECUTION_BLOCKED,
    InvalidAgentTaskRecoveryExecutionPreconditionRevalidationError,
    LLMAgentTaskRecoveryExecutionPreconditionDriftService,
    LLMAgentTaskRecoveryExecutionPreconditionRevalidationService,
    LLMAgentTaskRecoveryExecutionPreconditionSnapshotService,
    LLMAgentTaskRecoveryExecutionPreconditionValidationService,
    REVALIDATION_FAILED,
    REVALIDATION_REPLACED,
    REVALIDATION_REUSED,
)
from backend.agent_task_recovery_guardrails import (
    AgentTaskRecoveryPreflightResult,
    InMemoryAgentTaskRecoveryPreflightAuthorizationStore,
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
    authorization_store = InMemoryAgentTaskRecoveryPreflightAuthorizationStore()
    authorization_service = LLMAgentTaskRecoveryPreflightAuthorizationService(
        preflight_store=preflight_store, approval_service=approval_service,
        invalidation_service=invalidation_service, evaluation_service=evaluation_service,
        store=authorization_store,
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
    drift_service = LLMAgentTaskRecoveryExecutionPreconditionDriftService(validation_service=validation_service)
    revalidation_service = LLMAgentTaskRecoveryExecutionPreconditionRevalidationService(
        snapshot_service=snapshot_service, drift_service=drift_service,
        authorization_service=authorization_service, authorization_store=authorization_store,
        preflight_store=preflight_store,
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
        "drift_service": drift_service,
        "revalidation_service": revalidation_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _authorize_current(s, task_id="task-1"):
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    authorization = s["authorization_service"].authorize(task_id, preflight.preflight_id)
    return preflight, authorization


def _authorize_manual(s, task_id, plan):
    # A distinct `reason` keeps this preflight's own identity fields
    # (plan/decision/blocking_reasons/warnings) genuinely different from
    # any preflight_service.run() already saved for task_id, so save()
    # never dedupes it into the same, already-current preflight_id.
    preflight = s["preflight_store"].save(
        AgentTaskRecoveryPreflightResult(
            task_id=task_id, plan=plan, guard_result=None, decision=ALLOW,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    authorization = s["authorization_service"].authorize(task_id, preflight.preflight_id)
    return preflight, authorization


def test_no_blocking_drift_reuses_existing_snapshot():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    result = s["revalidation_service"].revalidate("task-1", snapshot.snapshot_id)

    assert result.action == REVALIDATION_REUSED
    assert result.new_snapshot_id == snapshot.snapshot_id
    assert result.old_snapshot_id == snapshot.snapshot_id
    assert result.eligible is True


def test_revalidate_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionRevalidationError):
        s["revalidation_service"].revalidate("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionRevalidationError):
        s["revalidation_service"].revalidate("task-1", "")


def test_revalidate_rejects_unknown_snapshot():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionRevalidationError):
        s["revalidation_service"].revalidate("task-1", "never-existed")


def test_failed_authorization_without_a_replacement_fails_closed():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="operator revoked")

    result = s["revalidation_service"].revalidate("task-1", snapshot.snapshot_id)

    assert result.action == REVALIDATION_FAILED
    assert result.new_snapshot_id is None
    assert result.eligible is False
    assert "no active authorization" in result.reason


def test_blocking_drift_that_persists_produces_a_new_but_still_failed_snapshot():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    s["readiness"].set(dependencies_passed=False)

    result = s["revalidation_service"].revalidate("task-1", snapshot.snapshot_id)

    assert result.old_drift.category == DRIFT_EXECUTION_BLOCKED
    assert result.action == REVALIDATION_FAILED
    assert result.new_snapshot_id is not None
    assert result.new_snapshot_id != snapshot.snapshot_id
    assert result.eligible is False

    # History is preserved -- the original snapshot is untouched.
    original = s["snapshot_service"].get("task-1", snapshot.snapshot_id)
    assert original == snapshot


def test_revoked_authorization_rebuilds_against_a_fresh_authorization():
    s = _stack()
    _fail_task(s["event_service"])
    preflight1, authorization1 = _authorize_current(s)
    snapshot1 = s["snapshot_service"].capture("task-1", authorization1.authorization_id)

    s["authorization_service"].revoke("task-1", authorization1.authorization_id, reason="operator revoked")

    # A fresh preflight (distinct identity, but still guard-ALLOW under the
    # SAME live conditions) becomes task-1's own current one, approved and
    # authorized afresh.
    plan2 = preflight1.plan.__class__(
        task_id="task-1", failure_event_id=preflight1.plan.failure_event_id,
        failure_category=preflight1.plan.failure_category, recommended_action=RECOVERY_ACTION_RETRY,
        reason="re-approved after manual review", priority=preflight1.plan.priority, blocking_conditions=(),
    )
    _, authorization2 = _authorize_manual(s, "task-1", plan2)

    result = s["revalidation_service"].revalidate("task-1", snapshot1.snapshot_id)

    assert result.old_drift.category == DRIFT_EXECUTION_BLOCKED
    assert result.action == REVALIDATION_REPLACED
    assert result.new_snapshot_id is not None
    assert result.new_snapshot_id != snapshot1.snapshot_id
    assert result.eligible is True

    new_snapshot = s["snapshot_service"].get("task-1", result.new_snapshot_id)
    assert new_snapshot.authorization_id == authorization2.authorization_id

    # The superseded snapshot's own record is never mutated.
    original = s["snapshot_service"].get("task-1", snapshot1.snapshot_id)
    assert original == snapshot1
    assert original.authorization_id == authorization1.authorization_id


def test_repeated_revalidation_is_idempotent_once_a_valid_snapshot_exists():
    s = _stack()
    _fail_task(s["event_service"])
    preflight1, authorization1 = _authorize_current(s)
    snapshot1 = s["snapshot_service"].capture("task-1", authorization1.authorization_id)

    s["authorization_service"].revoke("task-1", authorization1.authorization_id, reason="operator revoked")
    plan2 = preflight1.plan.__class__(
        task_id="task-1", failure_event_id=preflight1.plan.failure_event_id,
        failure_category=preflight1.plan.failure_category, recommended_action=RECOVERY_ACTION_RETRY,
        reason="re-approved after manual review", priority=preflight1.plan.priority, blocking_conditions=(),
    )
    _authorize_manual(s, "task-1", plan2)

    first = s["revalidation_service"].revalidate("task-1", snapshot1.snapshot_id)
    assert first.action == REVALIDATION_REPLACED

    second = s["revalidation_service"].revalidate("task-1", snapshot1.snapshot_id)

    assert second.action == REVALIDATION_REUSED
    assert second.new_snapshot_id == first.new_snapshot_id
    assert second.eligible is True
