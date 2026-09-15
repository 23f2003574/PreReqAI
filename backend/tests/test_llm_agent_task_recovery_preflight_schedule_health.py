from dataclasses import replace
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
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService, RetryEligibilityResult
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
    DEGRADED,
    HEALTH_BLOCKED,
    HEALTHY,
    DEFAULT_SCHEDULE_EXPIRATION_TTL,
    InvalidAgentTaskRecoveryScheduleHealthError,
    LLMAgentTaskRecoveryPreflightScheduleBackoffService,
    LLMAgentTaskRecoveryPreflightScheduleCapacityService,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
    LLMAgentTaskRecoveryPreflightScheduleExpirationService,
    LLMAgentTaskRecoveryPreflightScheduleHealthService,
    LLMAgentTaskRecoveryPreflightScheduleRecoveryService,
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
    def enqueue(self, task_id):
        return type("Entry", (), {"task_id": task_id})()


def _stack(with_expiration=False, with_capacity=False, with_backoff=False, dispatch_queue_service=None):
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
        scheduling_service=scheduling_service, validation_service=schedule_validation_service,
        queue_service=dispatch_queue_service,
    )
    expiration_service = None
    if with_expiration:
        expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(
            scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        )
    recovery_service = LLMAgentTaskRecoveryPreflightScheduleRecoveryService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        validation_service=schedule_validation_service, expiration_service=expiration_service,
    )
    capacity_service = None
    if with_capacity:
        capacity_service = LLMAgentTaskRecoveryPreflightScheduleCapacityService(
            validation_service=schedule_validation_service,
        )
    backoff_service = None
    lifecycle_service = None
    if with_backoff:
        lifecycle_service = LLMAgentTaskLifecycleService()
        readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
        queue_service = LLMAgentTaskQueueService(readiness_service)
        dead_letter_service = LLMAgentTaskDeadLetterService(queue_service, lifecycle_service)
        eligibility_service = LLMAgentTaskQueueRetryEligibilityService(
            lifecycle_service, readiness_service, dead_letter_service
        )
        retry_scheduler = LLMAgentTaskRetryScheduler(eligibility_service)
        backoff_service = LLMAgentTaskRecoveryPreflightScheduleBackoffService(
            retry_scheduler=retry_scheduler, scheduling_service=scheduling_service,
        )

    health_service = LLMAgentTaskRecoveryPreflightScheduleHealthService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service, recovery_service=recovery_service,
        expiration_service=expiration_service, capacity_service=capacity_service, backoff_service=backoff_service,
    )
    return {
        "event_service": event_service,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "scheduling_service": scheduling_service,
        "dispatch_service": dispatch_service,
        "health_service": health_service,
        "lifecycle_service": lifecycle_service,
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


def _real_task(lifecycle_service, **overrides):
    definition = {"agent_id": "a", "scope_id": "s", "objective": "recover"}
    definition.update(overrides)
    task = lifecycle_service.create(definition)
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


# --- healthy --------------------------------------------------------------


def test_fully_dispatched_schedule_is_healthy():
    s = _stack(dispatch_queue_service=_FakeQueueService())
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    result = s["health_service"].assess("task-1", now=NOW)

    assert result.status == HEALTHY
    assert result.issues == ()


def test_scoped_assess_for_healthy_schedule():
    s = _stack(dispatch_queue_service=_FakeQueueService())
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    result = s["health_service"].assess("task-1", schedule_id=schedule.schedule_id, now=NOW)
    assert result.status == HEALTHY


# --- degraded --------------------------------------------------------------


def test_never_dispatched_due_schedule_is_degraded():
    s = _stack()
    _scheduled(s)

    result = s["health_service"].assess("task-1", now=NOW)

    assert result.status == DEGRADED
    assert any(issue.code == "orphaned_dispatch" for issue in result.issues)


def test_invalidated_schedule_is_degraded():
    s = _stack()
    _scheduled(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    result = s["health_service"].assess("task-1", now=NOW)

    assert result.status == DEGRADED
    assert any(issue.code == "invalidated" for issue in result.issues)


def test_expired_schedule_is_degraded():
    ttl = DEFAULT_SCHEDULE_EXPIRATION_TTL
    s = _stack(with_expiration=True)
    _scheduled(s, execute_at=NOW - ttl - timedelta(minutes=1))

    result = s["health_service"].assess("task-1", now=NOW)

    assert result.status == DEGRADED
    assert any(issue.code == "expired" for issue in result.issues)


def test_duplicate_active_schedule_is_degraded():
    s = _stack()
    _fail_task(s["event_service"], task_id="task-1")
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)
    s["approval_service"].approve("task-1", preflight.preflight_id, actor="alice")
    first = s["scheduling_service"].schedule("task-1", preflight.preflight_id)
    # Directly persist a second SCHEDULED record for the identical
    # preflight_id, bypassing schedule()'s own idempotency check --
    # simulates the "inconsistent schedule state" Commit #4 detects.
    duplicate = replace(first, schedule_id="dup-schedule")
    s["scheduling_service"]._store.save(duplicate)

    result = s["health_service"].assess("task-1", now=NOW)

    assert result.status == DEGRADED
    assert any(issue.code == "duplicate_active_schedule" for issue in result.issues)


# --- blocked --------------------------------------------------------------


def test_ambiguous_dispatch_state_is_blocked():
    s = _stack()
    schedule = _scheduled(s)
    d1 = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    corrupted = replace(d1, dispatch_id="dispatch-2")
    s["dispatch_service"]._store.save(corrupted)

    result = s["health_service"].assess("task-1", now=NOW)

    assert result.status == HEALTH_BLOCKED
    assert any(issue.code == "inconsistent_schedule_state" for issue in result.issues)


def test_retry_exhausted_is_blocked():
    s = _stack(with_backoff=True)
    task = _real_task(s["lifecycle_service"], attempt_count=3, max_attempts=3)
    _scheduled(s, task_id=task.task_id)

    result = s["health_service"].assess(task.task_id, now=NOW)

    assert result.status == HEALTH_BLOCKED
    assert any(issue.code == "retry_exhausted" for issue in result.issues)


# --- multiple simultaneous issues --------------------------------------------------------------


def test_multiple_simultaneous_issues_report_worst_status():
    s = _stack(with_expiration=True, with_capacity=True)
    _scheduled(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    result = s["health_service"].assess("task-1", now=NOW)

    codes = {issue.code for issue in result.issues}
    assert "invalidated" in codes
    assert "capacity_blocked" in codes
    assert result.status == DEGRADED  # invalidated + capacity_blocked are both DEGRADED, no BLOCKED signal here
    assert len(result.issues) >= 2


# --- empty-task cases --------------------------------------------------------------


def test_empty_task_assess_is_healthy():
    s = _stack()

    result = s["health_service"].assess("never-scheduled-task", now=NOW)

    assert result.status == HEALTHY
    assert result.issues == ()


def test_empty_task_summary_is_healthy():
    s = _stack()

    summary = s["health_service"].summary("never-scheduled-task", now=NOW)

    assert summary.status == HEALTHY
    assert summary.schedule_count == 0
    assert summary.issue_count == 0


# --- summary + misc --------------------------------------------------------------


def test_summary_rolls_up_across_schedules():
    s = _stack()
    _scheduled(s)

    summary = s["health_service"].summary("task-1", now=NOW)

    assert summary.schedule_count == 1
    assert summary.issue_count >= 1
    assert summary.status == DEGRADED


def test_assess_deterministic_for_same_now():
    s = _stack()
    _scheduled(s)

    first = s["health_service"].assess("task-1", now=NOW)
    second = s["health_service"].assess("task-1", now=NOW)

    assert first == second


def test_cancelled_schedule_never_reported_unhealthy():
    s = _stack()
    schedule = _scheduled(s)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="operator cancelled")

    result = s["health_service"].assess("task-1", now=NOW)

    assert result.status == HEALTHY
    assert result.issues == ()


def test_unknown_schedule_id_raises():
    s = _stack()
    _scheduled(s)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleHealthError):
        s["health_service"].assess("task-1", schedule_id="does-not-exist", now=NOW)


def test_blank_task_id_rejected():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleHealthError):
        s["health_service"].assess("", now=NOW)
