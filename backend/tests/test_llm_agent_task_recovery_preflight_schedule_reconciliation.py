from datetime import datetime, timedelta, timezone

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
from backend.agent_task_recovery_scheduling import (
    CANCELLED,
    SCHEDULED,
    AgentTaskRecoveryPreflightSchedule,
    InvalidAgentTaskRecoveryScheduleReconciliationError,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
    LLMAgentTaskRecoveryPreflightScheduleReconciliationService,
    LLMAgentTaskRecoveryPreflightSchedulingService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
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


def _stack(readiness=None):
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    replay_service = LLMAgentTaskEventReplayService(query_service=query_service)

    readiness = readiness if readiness is not None else _FakeReadinessService()
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
    scheduling_service = LLMAgentTaskRecoveryPreflightSchedulingService(
        approval_service=approval_service, authorization_service=authorization_service,
        validation_service=authorization_validation_service,
    )
    schedule_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
    )
    dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        validation_service=schedule_validation_service, scheduling_service=scheduling_service,
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightScheduleReconciliationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
        dispatch_service=dispatch_service,
    )
    return {
        "event_service": event_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "scheduling_service": scheduling_service,
        "dispatch_service": dispatch_service,
        "reconciliation_service": reconciliation_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _scheduled(s, task_id="task-1"):
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    schedule = s["scheduling_service"].schedule(task_id, preflight.preflight_id)
    return preflight, schedule


# --- valid schedules preserved --------------------------------------------------------------


def test_valid_schedule_is_preserved_unchanged():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)

    result = s["reconciliation_service"].reconcile_all("task-1")

    assert result.affected == ()
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == SCHEDULED


def test_reconcile_rejects_blank_task_id():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleReconciliationError):
        s["reconciliation_service"].reconcile_all("")


# --- stale preflight --------------------------------------------------------------


def test_invalidated_preflight_schedule_gets_cancelled():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    result = s["reconciliation_service"].reconcile_all("task-1")

    assert len(result.affected) == 1
    assert result.affected[0].schedule_id == schedule.schedule_id
    assert result.affected[0].new_status == CANCELLED
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == CANCELLED


# --- revoked authorization --------------------------------------------------------------


def test_revoked_authorization_schedule_gets_cancelled():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["authorization_service"].revoke("task-1", schedule.authorization_id, reason="revoked externally")

    result = s["reconciliation_service"].reconcile_all("task-1")

    assert len(result.affected) == 1
    assert "revoked" in result.affected[0].reason


# --- task-state changes --------------------------------------------------------------


def test_policy_blocked_schedule_gets_cancelled():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["readiness"].set(policy_passed=False)

    result = s["reconciliation_service"].reconcile_all("task-1")

    assert len(result.affected) == 1
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == CANCELLED


# --- mismatches --------------------------------------------------------------


def test_reconcile_one_schedule_from_wrong_task_is_a_no_op():
    s = _stack()
    _fail_task(s["event_service"], task_id="task-1")
    preflight, schedule = _scheduled(s, task_id="task-1")

    result = s["reconciliation_service"].reconcile("task-2", schedule.schedule_id)

    assert result.affected == ()
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == SCHEDULED


def test_reconcile_specific_schedule_id():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["invalidation_service"].invalidate("task-1", reason="found a problem")

    result = s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)

    assert len(result.affected) == 1
    assert result.affected[0].schedule_id == schedule.schedule_id


# --- duplicate schedules --------------------------------------------------------------


def test_duplicate_active_schedule_for_same_preflight_gets_cancelled():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)

    # Directly construct a second SCHEDULED record for the SAME preflight_id
    # (schedule() itself is idempotent and would never produce this).
    duplicate = AgentTaskRecoveryPreflightSchedule(
        task_id="task-1", preflight_id=preflight.preflight_id, authorization_id=schedule.authorization_id,
        execute_at=None, status=SCHEDULED, created_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        cancelled_at=None, cancellation_reason=None,
    )
    s["scheduling_service"]._store.save(duplicate)

    result = s["reconciliation_service"].reconcile_all("task-1")

    assert len(result.affected) == 1
    assert result.affected[0].schedule_id == duplicate.schedule_id
    assert "duplicate" in result.affected[0].reason
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == SCHEDULED
    assert s["scheduling_service"].get("task-1", duplicate.schedule_id).status == CANCELLED


# --- already-dispatched/cancelled schedules --------------------------------------------------------------


def test_already_dispatched_schedule_is_left_alone_even_if_invalidated_later():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    s["invalidation_service"].invalidate("task-1", reason="found a problem after dispatch")

    result = s["reconciliation_service"].reconcile_all("task-1")

    assert result.affected == ()
    # Reconciliation never cancels an already-dispatched schedule, even
    # though get()'s own live view now (correctly, independently) reports
    # it as invalidated -- the underlying STORED record is what matters.
    assert s["scheduling_service"]._store.get(schedule.schedule_id).status == SCHEDULED


def test_already_cancelled_schedule_produces_no_new_entry():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="manually cancelled")

    result = s["reconciliation_service"].reconcile_all("task-1")

    assert result.affected == ()


# --- idempotent reconciliation --------------------------------------------------------------


def test_reconciliation_is_idempotent():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["invalidation_service"].invalidate("task-1", reason="found a problem")

    first = s["reconciliation_service"].reconcile_all("task-1")
    second = s["reconciliation_service"].reconcile_all("task-1")

    assert len(first.affected) == 1
    assert second.affected == ()
