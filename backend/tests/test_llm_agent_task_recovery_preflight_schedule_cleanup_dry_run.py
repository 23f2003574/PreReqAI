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
    InvalidAgentTaskRecoveryScheduleCleanupDryRunError,
    LLMAgentTaskRecoveryPreflightScheduleCleanupDryRunService,
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
    dry_run_service = LLMAgentTaskRecoveryPreflightScheduleCleanupDryRunService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        cleanup_service=cleanup_service, idempotency_service=idempotency_service,
    )
    return {
        "dry_run_service": dry_run_service,
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


def _snapshot(s, task_id="task-1"):
    return (s["scheduling_service"].list(task_id), s["dispatch_service"].list(task_id))


def _plan(s, now=NOW):
    return s["dry_run_service"].dry_run("task-1", now=now)


def test_empty_task_has_empty_plan():
    plan = _stack()["dry_run_service"].dry_run("no-such-task", now=NOW)

    assert (plan.candidates, plan.skipped, plan.failures) == ((), (), ())
    assert (plan.candidate_count, plan.skipped_count) == (0, 0)
    assert plan.planned_at == NOW


def test_expired_schedule_is_a_candidate_with_reason():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=OVERDUE)

    plan = _plan(s)

    assert plan.candidates == ((schedule.schedule_id, "expired"),)
    assert plan.skipped == ()


def test_invalidated_schedule_is_a_candidate_with_reason():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW + timedelta(hours=1))
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    assert _plan(s).candidates == ((schedule.schedule_id, "invalidated"),)


def test_active_schedule_is_skipped_as_still_active():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW + timedelta(hours=1))

    plan = _plan(s)

    assert plan.candidates == ()
    assert plan.skipped == ((schedule.schedule_id, STILL_ACTIVE),)


def test_cancelled_and_dispatched_schedules_are_skipped():
    s = _stack(max_overdue_age=TTL)
    cancelled = _scheduled(s, task_id="task-1", execute_at=OVERDUE)
    s["scheduling_service"].cancel("task-1", cancelled.schedule_id, reason="manual")

    assert _plan(s).skipped == ((cancelled.schedule_id, ALREADY_CLEANED),)

    s2 = _stack(max_overdue_age=TTL)
    dispatched = _scheduled(s2, execute_at=NOW - timedelta(hours=1))
    s2["dispatch_service"].dispatch("task-1", dispatched.schedule_id)

    assert _plan(s2, now=NOW + TTL * 2).skipped == ((dispatched.schedule_id, DISPATCHED),)


def test_dry_run_matches_what_real_cleanup_then_does():
    s = _stack(max_overdue_age=TTL)
    _scheduled(s, execute_at=OVERDUE)
    _scheduled(s, execute_at=NOW + timedelta(hours=1))
    dispatched = _scheduled(s, execute_at=NOW - timedelta(hours=1))
    s["dispatch_service"].dispatch("task-1", dispatched.schedule_id)
    plan = _plan(s)

    result = s["cleanup_service"].cleanup("task-1", now=NOW)

    assert plan.candidates == result.cleaned_reasons
    assert plan.candidate_count == result.cleaned_count
    assert tuple(i for i, _ in plan.skipped) == result.skipped_schedule_ids
    assert plan.skipped_count == result.skipped_count
    assert plan.failures == result.failures


def test_dry_run_causes_zero_state_changes_and_is_repeatable():
    s = _stack(max_overdue_age=TTL)
    _scheduled(s, execute_at=OVERDUE)
    _scheduled(s, execute_at=NOW + timedelta(hours=1))
    before = _snapshot(s)

    first = _plan(s)
    second = _plan(s)

    assert first.candidate_count >= 1
    assert first == second
    assert _snapshot(s) == before


def test_plan_still_lists_candidates_until_cleanup_actually_runs():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=OVERDUE)

    assert _plan(s).candidates == ((schedule.schedule_id, "expired"),)
    s["cleanup_service"].cleanup("task-1", now=NOW)

    plan = _plan(s)
    assert plan.candidates == ()
    assert plan.skipped == ((schedule.schedule_id, ALREADY_CLEANED),)


def test_failing_schedule_is_reported_as_failure_like_cleanup():
    class _Scheduling:
        def list(self, task_id):
            return [type("S", (), {"schedule_id": "s1", "status": "scheduled"})()]

    class _Idempotency:
        def check(self, task_id, schedule_id, now=None):
            raise RuntimeError("boom")

    service = LLMAgentTaskRecoveryPreflightScheduleCleanupDryRunService(
        scheduling_service=_Scheduling(), idempotency_service=_Idempotency()
    )

    plan = service.dry_run("task-1", now=NOW)

    assert plan.failures == (("s1", "boom"),)
    assert (plan.candidate_count, plan.skipped_count) == (0, 0)


@pytest.mark.parametrize("task_id", [None, "", 5])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupDryRunError):
        _stack()["dry_run_service"].dry_run(task_id)


def test_invalid_now_is_rejected():
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupDryRunError):
        _stack()["dry_run_service"].dry_run("task-1", now="soon")
