import pytest

from backend.agent_task_event_analytics import LLMAgentTaskEventFailureClassifier, LLMAgentTaskEventFailureRecoveryPlanner
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
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    InMemoryAgentTaskRecoveryExecutionPreconditionSnapshotStore,
    InvalidAgentTaskRecoveryExecutionDecisionStalenessError,
    LLMAgentTaskRecoveryExecutionDecisionStalenessService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
    LLMAgentTaskRecoveryExecutionPreconditionDriftService,
    LLMAgentTaskRecoveryExecutionPreconditionSnapshotService,
    LLMAgentTaskRecoveryExecutionPreconditionValidationService,
)
from backend.agent_task_recovery_guardrails import (
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
    snapshot_store = InMemoryAgentTaskRecoveryExecutionPreconditionSnapshotStore()
    snapshot_service = LLMAgentTaskRecoveryExecutionPreconditionSnapshotService(
        authorization_service=authorization_service, preflight_store=preflight_store,
        retry_eligibility_service=retry_eligibility, readiness_service=readiness, store=snapshot_store,
    )
    validation_service = LLMAgentTaskRecoveryExecutionPreconditionValidationService(
        snapshot_service=snapshot_service, guard_service=guard,
        authorization_validation_service=authorization_validation_service,
    )
    drift_service = LLMAgentTaskRecoveryExecutionPreconditionDriftService(validation_service=validation_service)
    decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    staleness_service = LLMAgentTaskRecoveryExecutionDecisionStalenessService(
        decision_store=decision_store, snapshot_service=snapshot_service, drift_service=drift_service,
        authorization_service=authorization_service,
    )
    return {
        "event_service": event_service, "readiness": readiness, "retry_eligibility": retry_eligibility,
        "preflight_service": preflight_service, "preflight_store": preflight_store,
        "approval_service": approval_service, "authorization_service": authorization_service,
        "snapshot_service": snapshot_service, "snapshot_store": snapshot_store,
        "decision_store": decision_store, "staleness_service": staleness_service,
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


def _save_decision(s, snapshot):
    from datetime import datetime, timezone
    from backend.agent_task_recovery_execution_precondition_snapshots import (
        EXECUTION_DECISION_ALLOW,
        AgentTaskRecoveryExecutionPreconditionDecision,
    )

    return s["decision_store"].save(
        AgentTaskRecoveryExecutionPreconditionDecision(
            task_id="task-1", snapshot_id=snapshot.snapshot_id, authorization_id=snapshot.authorization_id,
            decision=EXECUTION_DECISION_ALLOW, reason="test reason", blocking_conditions=(), warnings=(),
            validation_result=None, drift_classification=None, approval_reconciliation=None,
            created_at=datetime.now(timezone.utc),
        )
    )


def test_unchanged_state_is_fresh():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)
    decision = _save_decision(s, snapshot)

    result = s["staleness_service"].check("task-1", decision.decision_id)

    assert result.status == FRESHNESS_FRESH
    assert result.current_state_version == result.decision_state_version == snapshot.snapshot_id


def test_newer_snapshot_for_same_authorization_is_stale():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot1 = s["snapshot_service"].capture("task-1", authorization.authorization_id)
    decision = _save_decision(s, snapshot1)

    snapshot2 = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    result = s["staleness_service"].check("task-1", decision.decision_id)

    assert result.status == FRESHNESS_STALE
    assert result.current_state_version == snapshot2.snapshot_id
    assert result.decision_state_version == snapshot1.snapshot_id


def test_authorization_change_is_stale():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)
    decision = _save_decision(s, snapshot)

    s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="operator revoked")

    result = s["staleness_service"].check("task-1", decision.decision_id)

    assert result.status == FRESHNESS_STALE


def test_repeated_checks_are_consistent():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)
    decision = _save_decision(s, snapshot)

    first = s["staleness_service"].check("task-1", decision.decision_id)
    second = s["staleness_service"].check("task-1", decision.decision_id)

    assert first.status == second.status == FRESHNESS_FRESH


def test_missing_decision_is_unknown():
    s = _stack()
    result = s["staleness_service"].check("task-1", "never-existed")

    assert result.status == FRESHNESS_UNKNOWN


def test_missing_freshness_evidence_is_unknown():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)
    decision = _save_decision(s, snapshot)

    # A drift service whose own validation stack lacks readiness/retry
    # collaborators cannot safely compare those fields against the
    # snapshot's own captured values -- required evidence is unavailable.
    unwired_snapshot_service = LLMAgentTaskRecoveryExecutionPreconditionSnapshotService(
        authorization_service=s["authorization_service"], preflight_store=s["preflight_store"],
        store=s["snapshot_store"],
    )
    unwired_validation_service = LLMAgentTaskRecoveryExecutionPreconditionValidationService(
        snapshot_service=unwired_snapshot_service
    )
    unwired_drift_service = LLMAgentTaskRecoveryExecutionPreconditionDriftService(
        validation_service=unwired_validation_service
    )
    staleness_service = LLMAgentTaskRecoveryExecutionDecisionStalenessService(
        decision_store=s["decision_store"], snapshot_service=unwired_snapshot_service,
        drift_service=unwired_drift_service, authorization_service=s["authorization_service"],
    )

    result = staleness_service.check("task-1", decision.decision_id)

    assert result.status == FRESHNESS_UNKNOWN


def test_check_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionStalenessError):
        s["staleness_service"].check("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionDecisionStalenessError):
        s["staleness_service"].check("task-1", "")
