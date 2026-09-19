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
    LLMAgentTaskRecoveryPreflightScheduleCleanupService,
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
    return {
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


def _stored(s, schedule_id):
    return s["scheduling_service"].get("task-1", schedule_id)


# --- active schedules are never touched --------------------------------------------------------------


def test_active_schedules_are_skipped_untouched():
    s = _stack(max_overdue_age=TTL)
    not_yet_due = _scheduled(s, execute_at=NOW + timedelta(hours=1))

    result = s["cleanup_service"].cleanup("task-1", now=NOW)

    assert result.cleaned_count == 0
    assert result.skipped_count == 1
    assert result.skipped_schedule_ids == (not_yet_due.schedule_id,)
    assert _stored(s, not_yet_due.schedule_id).status == SCHEDULED


def test_due_within_ttl_schedule_is_skipped_untouched():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW - timedelta(hours=1))

    result = s["cleanup_service"].cleanup("task-1", now=NOW)

    assert result.cleaned_schedule_ids == ()
    assert result.skipped_schedule_ids == (schedule.schedule_id,)
    assert _stored(s, schedule.schedule_id).status == SCHEDULED


# --- terminal schedules --------------------------------------------------------------


def test_expired_schedule_is_cleaned_and_history_preserved():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=OVERDUE)

    result = s["cleanup_service"].cleanup("task-1", now=NOW)

    assert result.cleaned_count == 1
    assert result.cleaned_schedule_ids == (schedule.schedule_id,)
    stored = _stored(s, schedule.schedule_id)
    assert stored.status == CANCELLED
    assert stored.cancellation_reason.startswith("expired:")
    assert [r.schedule_id for r in s["scheduling_service"].list("task-1")] == [schedule.schedule_id]


def test_invalidated_schedule_is_cleaned():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW + timedelta(hours=1))
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")
    assert _stored(s, schedule.schedule_id).status == INVALIDATED

    result = s["cleanup_service"].cleanup("task-1", now=NOW)

    assert result.cleaned_schedule_ids == (schedule.schedule_id,)
    assert _stored(s, schedule.schedule_id).status == CANCELLED


def test_already_cancelled_schedule_is_skipped_and_reason_kept():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=OVERDUE)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="manual")

    result = s["cleanup_service"].cleanup("task-1", now=NOW)

    assert result.cleaned_count == 0
    assert result.skipped_schedule_ids == (schedule.schedule_id,)
    assert _stored(s, schedule.schedule_id).cancellation_reason == "manual"


def test_dispatched_schedule_is_skipped_even_when_overdue():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW - timedelta(hours=1))
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    result = s["cleanup_service"].cleanup("task-1", now=NOW + TTL * 2)

    assert result.cleaned_count == 0
    assert result.skipped_schedule_ids == (schedule.schedule_id,)
    assert _stored(s, schedule.schedule_id).status == SCHEDULED


# --- idempotence and validation --------------------------------------------------------------


def test_cleanup_is_idempotent():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=OVERDUE)

    first = s["cleanup_service"].cleanup("task-1", now=NOW)
    second = s["cleanup_service"].cleanup("task-1", now=NOW)

    assert first.cleaned_schedule_ids == (schedule.schedule_id,)
    assert second.cleaned_count == 0
    assert second.skipped_schedule_ids == (schedule.schedule_id,)


def test_unknown_task_cleans_nothing():
    result = _stack()["cleanup_service"].cleanup("no-such-task", now=NOW)

    assert (result.cleaned_count, result.skipped_count) == (0, 0)


def test_only_the_named_task_is_cleaned():
    s = _stack(max_overdue_age=TTL)
    _scheduled(s, task_id="task-1", execute_at=OVERDUE)
    other = _scheduled(s, task_id="task-2", execute_at=OVERDUE)

    s["cleanup_service"].cleanup("task-1", now=NOW)

    assert s["scheduling_service"].get("task-2", other.schedule_id).status == SCHEDULED


@pytest.mark.parametrize("task_id", [None, "", 5])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupError):
        _stack()["cleanup_service"].cleanup(task_id)


def test_invalid_now_is_rejected():
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupError):
        _stack()["cleanup_service"].cleanup("task-1", now="soon")


def test_cleaned_reasons_pair_each_id_with_its_terminal_reason():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=OVERDUE)

    result = s["cleanup_service"].cleanup("task-1", now=NOW)

    assert result.cleaned_reasons == ((schedule.schedule_id, "expired"),)
    assert result.failures == ()
