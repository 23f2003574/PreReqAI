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
    INVALIDATED,
    SCHEDULED,
    InvalidAgentTaskRecoveryScheduleCleanupError,
    LLMAgentTaskRecoveryPreflightScheduleCleanupIdempotencyService,
    LLMAgentTaskRecoveryPreflightScheduleCleanupService,
    InvalidAgentTaskRecoveryScheduleCleanupIdempotencyError,
    ALREADY_CLEANED,
    CLEANUP_ELIGIBLE,
    STILL_ACTIVE,
    DISPATCHED,
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
    cleanup_service = LLMAgentTaskRecoveryPreflightScheduleCleanupService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        expiration_service=expiration_service,
    )
    idempotency_service = LLMAgentTaskRecoveryPreflightScheduleCleanupIdempotencyService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service, cleanup_service=cleanup_service
    )
    return {
        "idempotency_service": idempotency_service,
        "cleanup_service": cleanup_service,
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


TTL = timedelta(hours=24)
OVERDUE = NOW - TTL - timedelta(minutes=1)


def _check(s, schedule, now=NOW):
    return s["idempotency_service"].check("task-1", schedule.schedule_id, now=now)


def test_first_cleanup_eligible_then_already_cleaned():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=OVERDUE)

    before = _check(s, schedule)
    s["cleanup_service"].cleanup("task-1", now=NOW)
    after = _check(s, schedule)

    assert before.state == CLEANUP_ELIGIBLE
    assert before.reason == "expired"
    assert before.history_recorded is False
    assert after.state == ALREADY_CLEANED
    assert after.reason.startswith("expired:")
    assert after.history_recorded is True


def test_invalidated_schedule_is_eligible_then_already_cleaned():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW + timedelta(hours=1))
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    assert _check(s, schedule).state == CLEANUP_ELIGIBLE
    s["cleanup_service"].cleanup("task-1", now=NOW)
    assert _check(s, schedule).state == ALREADY_CLEANED


def test_repeated_cleanup_makes_no_second_transition():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=OVERDUE)

    s["cleanup_service"].cleanup("task-1", now=NOW)
    first = _check(s, schedule)
    second_pass = s["cleanup_service"].cleanup("task-1", now=NOW + timedelta(hours=5))
    second = _check(s, schedule, now=NOW + timedelta(hours=5))

    assert second_pass.cleaned_count == 0
    assert (second.state, second.reason, second.cleaned_at) == (first.state, first.reason, first.cleaned_at)


def test_active_schedule_is_still_active_and_never_modified():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW + timedelta(hours=1))

    assert _check(s, schedule).state == STILL_ACTIVE
    s["cleanup_service"].cleanup("task-1", now=NOW)

    assert _check(s, schedule).state == STILL_ACTIVE
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"


def test_check_is_read_only():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=OVERDUE)

    _check(s, schedule)

    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"


def test_dispatched_schedule_is_reported_dispatched():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW - timedelta(hours=1))
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    assert _check(s, schedule, now=NOW + TTL * 2).state == DISPATCHED


def test_cancelled_schedule_without_history_is_already_cleaned_but_flagged():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW + timedelta(hours=1))
    s["scheduling_service"].cancel("task-1", schedule.schedule_id)

    result = _check(s, schedule)

    assert result.state == ALREADY_CLEANED
    assert result.reason is None
    assert result.history_recorded is False


def test_missing_schedule_is_rejected():
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupIdempotencyError):
        _stack()["idempotency_service"].check("task-1", "no-such-schedule")


@pytest.mark.parametrize("task_id,schedule_id", [(None, "s"), ("", "s"), ("t", None), ("t", "")])
def test_invalid_ids_are_rejected(task_id, schedule_id):
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupIdempotencyError):
        _stack()["idempotency_service"].check(task_id, schedule_id)
