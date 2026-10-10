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
from backend.agent_task_lifecycle import FAILED, PLANNED, READY, LLMAgentTaskLifecycleService
from backend.agent_task_queue import LLMAgentTaskQueueService
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
from backend.agent_task_queue_retry_scheduler import LLMAgentTaskRetryScheduler
from backend.agent_task_readiness import AgentTaskReadinessCheck, AgentTaskReadinessResult, LLMAgentTaskReadinessService
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
    InvalidAgentTaskRecoveryScheduleBackoffError,
    LLMAgentTaskRecoveryPreflightScheduleBackoffService,
    LLMAgentTaskRecoveryPreflightSchedulingService,
)
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _FakeReadinessService:
    def __init__(self, ready=True, blocking=None):
        checks = [
            AgentTaskReadinessCheck(name="lifecycle_state", passed=True),
            AgentTaskReadinessCheck(name="dependencies", passed=True),
            AgentTaskReadinessCheck(name="policy", passed=ready, detail=None if ready else (blocking or "blocked")),
        ]
        self._result = AgentTaskReadinessResult(
            ready=ready, task_id="unused", blocking_reasons=[] if ready else [blocking or "blocked"],
            warnings=[], checks=checks,
        )

    def check(self, task_id):
        return self._result


class _FakeRetryEligibilityServiceForGuard:
    def check(self, task_id):
        return RetryEligibilityResult(task_id=task_id, eligible=True, reason="eligible")


class _FakeRetryScheduler:
    def get_retry_schedule(self, task_id):
        return None


class _FakeDeadLetterService:
    def get(self, task_id):
        return None


class _FakeReservationService:
    def is_reservation_valid(self, task_id):
        return False


def _queue_lifecycle_stack():
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    dead_letter_service = LLMAgentTaskDeadLetterService(queue_service, lifecycle_service)
    eligibility_service = LLMAgentTaskQueueRetryEligibilityService(
        lifecycle_service, readiness_service, dead_letter_service
    )
    retry_scheduler = LLMAgentTaskRetryScheduler(eligibility_service)
    return lifecycle_service, retry_scheduler


def _real_task(lifecycle_service, **overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "recover"}
    definition.update(overrides)
    task = lifecycle_service.create(definition)
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


def _recovery_stack(task_id):
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    replay_service = LLMAgentTaskEventReplayService(query_service=query_service)

    readiness = _FakeReadinessService()
    retry_eligibility = _FakeRetryEligibilityServiceForGuard()

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
    return {
        "event_service": event_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "scheduling_service": scheduling_service,
    }


def _fail_task(event_service, task_id):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _scheduled(r, task_id):
    _fail_task(r["event_service"], task_id)
    preflight = r["preflight_store"].save(r["preflight_service"].run(task_id))
    r["approval_service"].request(task_id, preflight.preflight_id)
    r["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    return r["scheduling_service"].schedule(task_id, preflight.preflight_id)


def _stack(**definition_overrides):
    lifecycle_service, retry_scheduler = _queue_lifecycle_stack()
    task = _real_task(lifecycle_service, **definition_overrides)
    r = _recovery_stack(task.task_id)
    backoff_service = LLMAgentTaskRecoveryPreflightScheduleBackoffService(
        retry_scheduler=retry_scheduler, scheduling_service=r["scheduling_service"]
    )
    schedule = _scheduled(r, task.task_id)
    return task.task_id, r, backoff_service, schedule


# --- first attempt / deterministic calculation --------------------------------------------------------------


def test_first_attempt_no_backoff_constraint():
    task_id, r, backoff_service, schedule = _stack()  # no retry metadata at all

    result = backoff_service.calculate(task_id, schedule.schedule_id, now=NOW)

    assert result.eligible is True
    assert result.attempt == 1
    assert result.delay == timedelta(0)
    assert result.execute_at == NOW
    assert result.blocking_reasons == ()


def test_calculation_is_deterministic():
    task_id, r, backoff_service, schedule = _stack(attempt_count=1, max_attempts=5)

    first = backoff_service.calculate(task_id, schedule.schedule_id, now=NOW)
    second = backoff_service.calculate(task_id, schedule.schedule_id, now=NOW)

    assert first == second


def test_blank_task_id_rejected():
    task_id, r, backoff_service, schedule = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleBackoffError):
        backoff_service.calculate("", schedule.schedule_id, now=NOW)


# --- increasing retry history --------------------------------------------------------------


def test_increasing_attempt_count_reflected():
    task_id, r, backoff_service, schedule = _stack(attempt_count=2, max_attempts=5)

    result = backoff_service.calculate(task_id, schedule.schedule_id, now=NOW)

    assert result.attempt == 3
    assert result.remaining_attempts == 3


# --- retry-limit exhaustion --------------------------------------------------------------


def test_retry_limit_exhausted_blocks_calculation():
    task_id, r, backoff_service, schedule = _stack(attempt_count=3, max_attempts=3)

    result = backoff_service.calculate(task_id, schedule.schedule_id, now=NOW)

    assert result.eligible is False
    assert result.dead_letter_required is True
    assert any("exhausted" in reason for reason in result.blocking_reasons)


# --- deadline/budget limits (readiness/policy) --------------------------------------------------------------


def test_policy_blocked_task_is_not_eligible():
    lifecycle_service, retry_scheduler = _queue_lifecycle_stack()
    task = lifecycle_service.create({"agent_id": "a", "scope_id": "s", "objective": "recover", "retryable": False})
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    r = _recovery_stack(task.task_id)
    backoff_service = LLMAgentTaskRecoveryPreflightScheduleBackoffService(
        retry_scheduler=retry_scheduler, scheduling_service=r["scheduling_service"]
    )
    schedule = _scheduled(r, task.task_id)

    result = backoff_service.calculate(task.task_id, schedule.schedule_id, now=NOW)

    assert result.eligible is False
    assert result.dead_letter_required is True


# --- invalid schedules --------------------------------------------------------------


def test_cancelled_schedule_cannot_be_calculated_eligible():
    task_id, r, backoff_service, schedule = _stack()
    r["scheduling_service"].cancel(task_id, schedule.schedule_id)

    result = backoff_service.calculate(task_id, schedule.schedule_id, now=NOW)

    assert result.eligible is False
    assert any("cancelled" in reason for reason in result.blocking_reasons)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleBackoffError):
        backoff_service.reschedule(task_id, schedule.schedule_id, now=NOW)


def test_invalidated_schedule_cannot_be_rescheduled():
    task_id, r, backoff_service, schedule = _stack()
    r["invalidation_service"].invalidate(task_id, reason="operator flagged this")

    with pytest.raises(InvalidAgentTaskRecoveryScheduleBackoffError):
        backoff_service.reschedule(task_id, schedule.schedule_id, now=NOW)


def test_unknown_schedule_id_rejected():
    task_id, r, backoff_service, schedule = _stack()
    result = backoff_service.calculate(task_id, "does-not-exist", now=NOW)
    assert result.eligible is False


def test_retry_scheduler_required():
    with pytest.raises(InvalidAgentTaskRecoveryScheduleBackoffError):
        LLMAgentTaskRecoveryPreflightScheduleBackoffService(retry_scheduler=None)


# --- rescheduling + preservation of schedule history --------------------------------------------------------------


def test_reschedule_creates_new_schedule_and_preserves_old():
    policy_overrides = {"attempt_count": 1, "max_attempts": 5}
    task_id, r, backoff_service, schedule = _stack(**policy_overrides)

    new_schedule = backoff_service.reschedule(task_id, schedule.schedule_id, now=NOW)

    assert new_schedule.schedule_id != schedule.schedule_id
    assert new_schedule.preflight_id == schedule.preflight_id
    assert new_schedule.execute_at == NOW  # no backoff metadata -> immediate

    history = r["scheduling_service"].list(task_id)
    ids = {entry.schedule_id: entry for entry in history}
    assert schedule.schedule_id in ids
    assert ids[schedule.schedule_id].status == CANCELLED
    assert new_schedule.schedule_id in ids


def test_reschedule_never_executes_recovery():
    task_id, r, backoff_service, schedule = _stack(attempt_count=1, max_attempts=5)
    before = r["preflight_store"].get(task_id)

    backoff_service.reschedule(task_id, schedule.schedule_id, now=NOW)

    after = r["preflight_store"].get(task_id)
    assert before == after
