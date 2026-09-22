from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_events import (
    LIFECYCLE_TRANSITIONED,
    InMemoryAgentTaskEventStore,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventReplayService,
    LLMAgentTaskEventService,
)
from backend.agent_task_event_analytics import LLMAgentTaskEventFailureClassifier, LLMAgentTaskEventFailureRecoveryPlanner
from backend.agent_task_lifecycle import FAILED, PLANNED
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult
from backend.agent_task_readiness import AgentTaskReadinessCheck, AgentTaskReadinessResult
from backend.agent_task_recovery_execution_precondition_snapshots import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    AgentTaskRecoveryExecutionPreconditionDecision,
    InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError,
    LLMAgentTaskRecoveryExecutionPreconditionApprovalReconciliationService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
    LLMAgentTaskRecoveryExecutionPreconditionDriftService,
    LLMAgentTaskRecoveryExecutionPreconditionRevalidationService,
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

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _decision(task_id="task-1", snapshot_id="snap-1", decision=EXECUTION_DECISION_ALLOW, created_at=NOW):
    return AgentTaskRecoveryExecutionPreconditionDecision(
        task_id=task_id, snapshot_id=snapshot_id, authorization_id="auth-1", decision=decision,
        reason="test reason", blocking_conditions=(), warnings=(), validation_result=None,
        drift_classification=None, approval_reconciliation=None, created_at=created_at,
    )


class _FailingRawStore:
    def save(self, record):
        raise RuntimeError("disk is full")

    def get(self, decision_id):
        return None

    def list_for_task(self, task_id):
        return []


def test_save_and_get_a_decision():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    decision = _decision()

    saved = store.save(decision)

    assert saved.decision_id == decision.decision_id
    fetched = store.get(decision.decision_id)
    assert fetched == decision


def test_get_missing_decision_returns_none():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    assert store.get("never-existed") is None


def test_latest_returns_none_when_nothing_recorded():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    assert store.latest("task-1") is None
    assert store.history("task-1") == []


def test_latest_and_history_across_multiple_decisions():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    first = _decision(decision=EXECUTION_DECISION_BLOCK, created_at=NOW)
    second = _decision(decision=EXECUTION_DECISION_REVIEW, created_at=NOW + timedelta(seconds=1))
    third = _decision(decision=EXECUTION_DECISION_ALLOW, created_at=NOW + timedelta(seconds=2))

    store.save(first)
    store.save(third)
    store.save(second)

    history = store.history("task-1")
    assert [d.decision_id for d in history] == [first.decision_id, second.decision_id, third.decision_id]
    assert store.latest("task-1").decision_id == third.decision_id


def test_decisions_for_different_tasks_are_isolated():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    store.save(_decision(task_id="task-1"))
    store.save(_decision(task_id="task-2"))

    assert len(store.history("task-1")) == 1
    assert len(store.history("task-2")) == 1


def test_repeated_evaluation_appends_never_mutates():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    original = _decision()
    saved = store.save(original)

    saved.__dict__  # dataclass is frozen; attempting mutation raises
    with pytest.raises(Exception):
        saved.decision = EXECUTION_DECISION_BLOCK

    store.save(_decision())
    assert len(store.history("task-1")) == 2
    assert store.get(original.decision_id) == original


def test_save_rejects_non_decision_objects():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError):
        store.save("not a decision")


def test_persistence_failure_raises_rather_than_silently_succeeding():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore(store=_FailingRawStore())
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError):
        store.save(_decision())


def test_lookup_rejects_blank_arguments():
    store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError):
        store.get("")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError):
        store.latest("")
    with pytest.raises(InvalidAgentTaskRecoveryExecutionPreconditionDecisionPersistenceError):
        store.history("")


# --- integration with the canonical decision service ------------------------


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
    decision_store = LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
    decision_service = LLMAgentTaskRecoveryExecutionPreconditionDecisionService(
        snapshot_service=snapshot_service, approval_reconciliation_service=reconciliation_service,
        store=decision_store,
    )
    return {
        "event_service": event_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "snapshot_service": snapshot_service,
        "decision_service": decision_service,
        "decision_store": decision_store,
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


def test_decide_persists_allow_decision():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    decision = s["decision_service"].decide("task-1", snapshot.snapshot_id)

    assert decision.decision == EXECUTION_DECISION_ALLOW
    stored = s["decision_store"].get(decision.decision_id)
    assert stored == decision
    assert s["decision_store"].latest("task-1") == decision


def test_decide_persists_block_decision_for_missing_snapshot():
    s = _stack()
    decision = s["decision_service"].decide("task-1", "never-existed")

    assert decision.decision == EXECUTION_DECISION_BLOCK
    assert s["decision_store"].get(decision.decision_id) == decision


def test_repeated_decide_calls_accumulate_history():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorize_current(s)
    snapshot = s["snapshot_service"].capture("task-1", authorization.authorization_id)

    first = s["decision_service"].decide("task-1", snapshot.snapshot_id)
    second = s["decision_service"].decide("task-1", snapshot.snapshot_id)

    history = s["decision_store"].history("task-1")
    assert [d.decision_id for d in history] == [first.decision_id, second.decision_id]
    assert s["decision_store"].latest("task-1").decision_id == second.decision_id
