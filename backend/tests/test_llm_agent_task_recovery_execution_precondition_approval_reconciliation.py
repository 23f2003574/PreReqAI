from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_RETRY,
    RECOVERY_PRIORITY_LOW,
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
    InvalidAgentTaskRecoveryExecutionPreconditionApprovalReconciliationError,
    LLMAgentTaskRecoveryExecutionPreconditionApprovalReconciliationService,
    LLMAgentTaskRecoveryExecutionPreconditionDriftService,
    LLMAgentTaskRecoveryExecutionPreconditionRevalidationService,
    LLMAgentTaskRecoveryExecutionPreconditionSnapshotService,
    LLMAgentTaskRecoveryExecutionPreconditionValidationService,
    RECONCILED_PRESERVED,
    RECONCILED_REQUIRES_REVIEW,
    RECONCILED_REVOKED,
)
from backend.agent_task_recovery_guardrails import (
    APPROVED,
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
    reconciliation_service = LLMAgentTaskRecoveryExecutionPreconditionApprovalReconciliationService(
        snapshot_service=snapshot_service, revalidation_service=revalidation_service,
        approval_service=approval_service,
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
        "reconciliation_service": reconciliation_service,
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


def test_unchanged_snapshot_preserves_approval():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    result = s["reconciliation_service"].reconcile("task-1", snapshot.snapshot_id)

    assert result.state == RECONCILED_PRESERVED
    assert result.current_snapshot_id == snapshot.snapshot_id
    assert result.current_approval == result.previous_approval
    assert result.current_approval.status == APPROVED


def test_reconcile_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionApprovalReconciliationError):
        s["reconciliation_service"].reconcile("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionApprovalReconciliationError):
        s["reconciliation_service"].reconcile("task-1", "")


def test_reconcile_rejects_unknown_snapshot():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionApprovalReconciliationError):
        s["reconciliation_service"].reconcile("task-1", "never-existed")


def test_material_drift_requires_review():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    s["readiness"].set(dependencies_passed=False)

    result = s["reconciliation_service"].reconcile("task-1", snapshot.snapshot_id)

    assert result.state == RECONCILED_REQUIRES_REVIEW
    assert "material drift" in result.reason
    assert result.current_snapshot_id is not None
    assert result.current_snapshot_id != snapshot.snapshot_id


def test_changed_recovery_action_requires_review():
    s = _stack()
    _fail_task(s["event_service"])
    preflight1, authorization1 = _authorize_current(s)
    snapshot1 = s["snapshot_service"].capture("task-1", authorization1.authorization_id)

    s["authorization_service"].revoke("task-1", authorization1.authorization_id, reason="operator revoked")
    plan2 = preflight1.plan.__class__(
        task_id="task-1", failure_event_id=preflight1.plan.failure_event_id,
        failure_category=preflight1.plan.failure_category, recommended_action=RECOVERY_ACTION_MARK_UNRECOVERABLE,
        reason="manually marked unrecoverable", priority=RECOVERY_PRIORITY_LOW, blocking_conditions=(),
    )
    _authorize_manual(s, "task-1", plan2)

    result = s["reconciliation_service"].reconcile("task-1", snapshot1.snapshot_id)

    assert result.state == RECONCILED_REQUIRES_REVIEW
    assert RECOVERY_ACTION_RETRY in result.reason
    assert RECOVERY_ACTION_MARK_UNRECOVERABLE in result.reason


def test_revoked_authorization_without_replacement_is_revoked():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="operator revoked")

    result = s["reconciliation_service"].reconcile("task-1", snapshot.snapshot_id)

    assert result.state == RECONCILED_REVOKED
    assert result.current_snapshot_id is None
    assert result.current_approval is None


def test_equivalent_revalidation_is_preserved_once_reapproved():
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

    first = s["reconciliation_service"].reconcile("task-1", snapshot1.snapshot_id)
    assert first.state == RECONCILED_REQUIRES_REVIEW

    second = s["reconciliation_service"].reconcile("task-1", snapshot1.snapshot_id)

    assert second.state == RECONCILED_PRESERVED
    assert second.current_snapshot_id == first.current_snapshot_id


def test_repeated_reconciliation_is_idempotent():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    first = s["reconciliation_service"].reconcile("task-1", snapshot.snapshot_id)
    second = s["reconciliation_service"].reconcile("task-1", snapshot.snapshot_id)

    assert first.state == second.state == RECONCILED_PRESERVED
    assert first.current_snapshot_id == second.current_snapshot_id
    assert first.reason == second.reason


def test_approval_history_is_never_mutated():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    original_approval = s["approval_service"].get("task-1", snapshot.preflight_id)

    s["readiness"].set(dependencies_passed=False)
    s["reconciliation_service"].reconcile("task-1", snapshot.snapshot_id)

    unchanged_approval = s["approval_service"].get("task-1", snapshot.preflight_id)
    assert unchanged_approval == original_approval
