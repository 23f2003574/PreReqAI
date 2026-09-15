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
    DUE,
    EXPIRED,
    NOT_APPLICABLE,
    NOT_YET_DUE,
    DEFAULT_SCHEDULE_EXPIRATION_TTL,
    InvalidAgentTaskRecoveryScheduleDispatchError,
    InvalidAgentTaskRecoveryScheduleExpirationError,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
    LLMAgentTaskRecoveryPreflightScheduleExpirationService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
    LLMAgentTaskRecoveryPreflightSchedulingService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


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


class _FakeQueueService:
    def __init__(self):
        self.enqueued = []

    def enqueue(self, task_id):
        self.enqueued.append(task_id)
        return type("Entry", (), {"task_id": task_id})()


def _stack(readiness=None, dispatch_service=None, max_overdue_age=None):
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
    dispatch_service = dispatch_service if dispatch_service is not None else LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        scheduling_service=scheduling_service, validation_service=schedule_validation_service,
    )
    expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service, max_overdue_age=max_overdue_age,
    )
    return {
        "event_service": event_service,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "scheduling_service": scheduling_service,
        "dispatch_service": dispatch_service,
        "expiration_service": expiration_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _scheduled(s, task_id="task-1", execute_at=None):
    _fail_task(s["event_service"], task_id=task_id)
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    return s["scheduling_service"].schedule(task_id, preflight.preflight_id, execute_at=execute_at)


# --- unexpired schedules --------------------------------------------------------------


def test_not_yet_due_schedule_is_not_expired():
    s = _stack()
    schedule = _scheduled(s, execute_at=NOW + timedelta(hours=1))

    result = s["expiration_service"].check("task-1", schedule.schedule_id, now=NOW)

    assert result.state == NOT_YET_DUE
    assert result.expired is False

    with pytest.raises(InvalidAgentTaskRecoveryScheduleExpirationError):
        s["expiration_service"].expire("task-1", schedule.schedule_id, now=NOW)


def test_due_but_within_ttl_is_not_expired():
    s = _stack(max_overdue_age=timedelta(hours=24))
    schedule = _scheduled(s, execute_at=NOW - timedelta(hours=1))

    result = s["expiration_service"].check("task-1", schedule.schedule_id, now=NOW)

    assert result.state == DUE
    assert result.expired is False


# --- exact deadline boundaries --------------------------------------------------------------


def test_exact_ttl_boundary_is_expired():
    ttl = timedelta(hours=24)
    s = _stack(max_overdue_age=ttl)
    execute_at = NOW - ttl
    schedule = _scheduled(s, execute_at=execute_at)

    result = s["expiration_service"].check("task-1", schedule.schedule_id, now=NOW)

    assert result.state == EXPIRED
    assert result.expired is True


def test_one_second_before_ttl_boundary_is_due():
    ttl = timedelta(hours=24)
    s = _stack(max_overdue_age=ttl)
    execute_at = NOW - ttl + timedelta(seconds=1)
    schedule = _scheduled(s, execute_at=execute_at)

    result = s["expiration_service"].check("task-1", schedule.schedule_id, now=NOW)

    assert result.state == DUE


def test_exact_execute_at_boundary_is_due_not_not_yet_due():
    s = _stack()
    schedule = _scheduled(s, execute_at=NOW)

    result = s["expiration_service"].check("task-1", schedule.schedule_id, now=NOW)

    assert result.state == DUE


# --- expired schedules --------------------------------------------------------------


def test_overdue_schedule_expires_and_persists():
    ttl = timedelta(hours=24)
    s = _stack(max_overdue_age=ttl)
    schedule = _scheduled(s, execute_at=NOW - ttl - timedelta(minutes=1))

    expired = s["expiration_service"].expire("task-1", schedule.schedule_id, now=NOW)

    assert expired.status == CANCELLED
    assert expired.cancellation_reason.startswith("expired:")

    stored = s["scheduling_service"].get("task-1", schedule.schedule_id)
    assert stored.status == CANCELLED


def test_expire_with_explicit_reason():
    ttl = timedelta(hours=24)
    s = _stack(max_overdue_age=ttl)
    schedule = _scheduled(s, execute_at=NOW - ttl - timedelta(minutes=1))

    expired = s["expiration_service"].expire("task-1", schedule.schedule_id, reason="ops override", now=NOW)

    assert expired.cancellation_reason == "expired: ops override"


# --- cancelled/dispatched schedules respected --------------------------------------------------------------


def test_already_cancelled_schedule_is_not_applicable():
    s = _stack()
    schedule = _scheduled(s)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="operator cancelled")

    result = s["expiration_service"].check("task-1", schedule.schedule_id, now=NOW)
    assert result.state == NOT_APPLICABLE

    unchanged = s["expiration_service"].expire("task-1", schedule.schedule_id, now=NOW)
    assert unchanged.cancellation_reason == "operator cancelled"


def test_dispatched_schedule_is_not_applicable():
    ttl = timedelta(hours=24)
    s = _stack(max_overdue_age=ttl)
    schedule = _scheduled(s, execute_at=NOW - ttl - timedelta(minutes=1))
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    result = s["expiration_service"].check("task-1", schedule.schedule_id, now=NOW)
    assert result.state == NOT_APPLICABLE

    unchanged = s["expiration_service"].expire("task-1", schedule.schedule_id, now=NOW)
    assert unchanged.status != CANCELLED


def test_invalidated_schedule_is_not_applicable():
    s = _stack()
    schedule = _scheduled(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    result = s["expiration_service"].check("task-1", schedule.schedule_id, now=NOW)
    assert result.state == NOT_APPLICABLE


# --- repeated expiration (idempotent) --------------------------------------------------------------


def test_repeated_expiration_is_idempotent():
    ttl = timedelta(hours=24)
    s = _stack(max_overdue_age=ttl)
    schedule = _scheduled(s, execute_at=NOW - ttl - timedelta(minutes=1))

    first = s["expiration_service"].expire("task-1", schedule.schedule_id, now=NOW)
    second = s["expiration_service"].expire("task-1", schedule.schedule_id, now=NOW + timedelta(hours=1))

    assert first.cancellation_reason == second.cancellation_reason
    assert first.cancelled_at == second.cancelled_at


# --- bulk due expiration --------------------------------------------------------------


def test_expire_due_only_expires_eligible_schedules():
    ttl = timedelta(hours=24)
    s = _stack(max_overdue_age=ttl)
    overdue = _scheduled(s, task_id="task-1", execute_at=NOW - ttl - timedelta(minutes=1))
    not_yet_due = _scheduled(s, task_id="task-2", execute_at=NOW + timedelta(hours=1))

    result = s["expiration_service"].expire_due("task-1", now=NOW)
    assert {e.schedule_id for e in result.affected} == {overdue.schedule_id}
    assert s["scheduling_service"].get("task-1", overdue.schedule_id).status == CANCELLED

    result2 = s["expiration_service"].expire_due("task-2", now=NOW)
    assert result2.affected == ()
    assert s["scheduling_service"].get("task-2", not_yet_due.schedule_id).status != CANCELLED


def test_expire_due_repeated_call_produces_no_new_entries():
    ttl = timedelta(hours=24)
    s = _stack(max_overdue_age=ttl)
    _scheduled(s, task_id="task-1", execute_at=NOW - ttl - timedelta(minutes=1))

    first = s["expiration_service"].expire_due("task-1", now=NOW)
    second = s["expiration_service"].expire_due("task-1", now=NOW + timedelta(hours=1))

    assert len(first.affected) == 1
    assert second.affected == ()


# --- persistence/history --------------------------------------------------------------


def test_expiration_preserves_original_schedule_fields():
    ttl = timedelta(hours=24)
    s = _stack(max_overdue_age=ttl)
    execute_at = NOW - ttl - timedelta(minutes=1)
    schedule = _scheduled(s, execute_at=execute_at)

    expired = s["expiration_service"].expire("task-1", schedule.schedule_id, now=NOW)

    assert expired.schedule_id == schedule.schedule_id
    assert expired.preflight_id == schedule.preflight_id
    assert expired.execute_at == execute_at
    assert expired.created_at == schedule.created_at


def test_unknown_schedule_id_raises():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleExpirationError):
        s["expiration_service"].check("task-1", "does-not-exist", now=NOW)


# --- proof expired schedules cannot dispatch --------------------------------------------------------------


def test_expired_schedule_cannot_dispatch():
    ttl = timedelta(hours=24)
    s = _stack(max_overdue_age=ttl)
    schedule = _scheduled(s, execute_at=NOW - ttl - timedelta(minutes=1))
    s["expiration_service"].expire("task-1", schedule.schedule_id, now=NOW)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
