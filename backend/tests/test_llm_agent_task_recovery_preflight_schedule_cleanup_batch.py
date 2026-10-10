from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

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
    BATCH_CLEANED,
    BATCH_FAILED,
    BATCH_SKIPPED,
    InvalidAgentTaskRecoveryScheduleCleanupBatchError,
    InvalidAgentTaskRecoveryScheduleCleanupBatchPlanError,
    LLMAgentTaskRecoveryPreflightScheduleCleanupBatchService,
    LLMAgentTaskRecoveryPreflightScheduleCleanupBatchPlanService,
    LLMAgentTaskRecoveryPreflightScheduleCleanupOrderingService,
    LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService,
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
    candidate_service = LLMAgentTaskRecoveryPreflightScheduleCleanupCandidateService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        expiration_service=expiration_service, cleanup_service=cleanup_service,
    )
    ordering_service = LLMAgentTaskRecoveryPreflightScheduleCleanupOrderingService(
        candidate_service=candidate_service
    )
    batch_plan_service = LLMAgentTaskRecoveryPreflightScheduleCleanupBatchPlanService(
        candidate_service=candidate_service, ordering_service=ordering_service
    )
    batch_service = LLMAgentTaskRecoveryPreflightScheduleCleanupBatchService(
        plan_service=batch_plan_service, cleanup_service=cleanup_service
    )
    return {
        "batch_service": batch_service,
        "batch_plan_service": batch_plan_service,
        "ordering_service": ordering_service,
        "candidate_service": candidate_service,
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


def _extra(s, base, execute_at, preflight_id):
    """Another schedule for base's task (a task's own preflight only ever
    backs one live schedule, so extras are saved straight to the store)."""
    return s["scheduling_service"]._store.save(
        replace(base, schedule_id=str(uuid4()), preflight_id=preflight_id, execute_at=execute_at,
                created_at=base.created_at + timedelta(seconds=int(preflight_id[1:])))
    )


TTL = timedelta(hours=24)
OVERDUE = NOW - TTL - timedelta(minutes=1)


class _FailingFor:
    """Real cleanup service, except it raises for the given schedule_ids."""

    def __init__(self, real, fail_ids):
        self._real, self._fail_ids = real, set(fail_ids)

    def clean_schedule(self, task_id, schedule_id, now=None):
        if schedule_id in self._fail_ids:
            raise RuntimeError("boom")
        return self._real.clean_schedule(task_id, schedule_id, now=now)


def _execute(s, plan=None):
    return s["batch_service"].execute("task-1", plan, now=NOW)


def _status(s, schedule_id):
    return s["scheduling_service"].get("task-1", schedule_id).status


def _mixed(s):
    expired_new = _scheduled(s, execute_at=OVERDUE - timedelta(minutes=30))
    expired_old = _extra(s, expired_new, OVERDUE - timedelta(hours=5), "p1")
    invalidated = _extra(s, expired_new, NOW + timedelta(hours=1), "p2")
    s["scheduling_service"]._store.save(replace(invalidated, authorization_id="no-such-authorization"))
    _extra(s, expired_new, NOW + timedelta(hours=1), "p3")
    dispatched = _extra(s, expired_new, NOW - timedelta(hours=1), "p4")
    s["dispatch_service"].dispatch("task-1", dispatched.schedule_id)
    cancelled = _extra(s, expired_new, OVERDUE, "p5")
    s["scheduling_service"].cancel("task-1", cancelled.schedule_id, reason="manual")
    return expired_new, expired_old, invalidated



def test_empty_plan_executes_nothing():
    result = _stack()["batch_service"].execute("no-such-task", now=NOW)

    assert (result.entries, result.cleaned_count, result.skipped_count, result.failed_count) == ((), 0, 0, 0)


def test_all_success_cleans_in_plan_order_and_preserves_history():
    s = _stack(max_overdue_age=TTL)
    expired_new, expired_old, invalidated = _mixed(s)
    plan = s["batch_plan_service"].plan("task-1", now=NOW)

    result = _execute(s, plan)

    assert [e.schedule_id for e in result.entries] == list(plan.schedule_ids)
    assert [(e.outcome, e.reason) for e in result.entries] == [
        (BATCH_CLEANED, "invalidated"), (BATCH_CLEANED, "expired"), (BATCH_CLEANED, "expired"),
    ]
    assert (result.cleaned_count, result.skipped_count, result.failed_count) == (3, 0, 0)
    for schedule in (expired_new, expired_old, invalidated):
        assert _status(s, schedule.schedule_id) == CANCELLED
    assert len(s["scheduling_service"].list("task-1")) == 6


def test_partial_failure_keeps_successful_cleanups():
    s = _stack(max_overdue_age=TTL)
    expired_new, expired_old, invalidated = _mixed(s)
    failing = _FailingFor(s["cleanup_service"], [expired_old.schedule_id])
    service = LLMAgentTaskRecoveryPreflightScheduleCleanupBatchService(
        plan_service=s["batch_plan_service"], cleanup_service=failing
    )

    result = service.execute("task-1", now=NOW)

    assert [e.outcome for e in result.entries] == [BATCH_CLEANED, BATCH_FAILED, BATCH_CLEANED]
    failed = result.entries[1]
    assert (failed.schedule_id, failed.error, failed.reason) == (expired_old.schedule_id, "boom", None)
    assert (result.cleaned_count, result.failed_count) == (2, 1)
    assert _status(s, invalidated.schedule_id) == CANCELLED
    assert _status(s, expired_new.schedule_id) == CANCELLED
    assert _status(s, expired_old.schedule_id) == "scheduled"


def test_repeated_execution_is_idempotent_and_keeps_first_history():
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    plan = s["batch_plan_service"].plan("task-1", now=NOW)
    _execute(s, plan)
    after_first = s["scheduling_service"].list("task-1")

    second = _execute(s, plan)

    assert (second.cleaned_count, second.skipped_count, second.failed_count) == (0, 3, 0)
    assert all(e.outcome == BATCH_SKIPPED for e in second.entries)
    assert s["scheduling_service"].list("task-1") == after_first
    assert _execute(s).entries == ()


def test_active_and_dispatched_schedules_are_never_touched_even_if_planned():
    s = _stack(max_overdue_age=TTL)
    expired = _scheduled(s, execute_at=OVERDUE)
    active = _extra(s, expired, NOW + timedelta(hours=1), "p1")
    dispatched = _extra(s, expired, NOW - timedelta(hours=1), "p2")
    s["dispatch_service"].dispatch("task-1", dispatched.schedule_id)
    forged = replace(
        s["batch_plan_service"].plan("task-1", now=NOW),
        schedule_ids=(active.schedule_id, dispatched.schedule_id, expired.schedule_id), count=3,
    )

    result = _execute(s, forged)

    assert [e.outcome for e in result.entries] == [BATCH_SKIPPED, BATCH_SKIPPED, BATCH_CLEANED]
    assert _status(s, active.schedule_id) == "scheduled"
    assert _status(s, dispatched.schedule_id) == "scheduled"
    assert _status(s, expired.schedule_id) == CANCELLED


def test_unknown_planned_schedule_is_a_failure_not_a_crash():
    s = _stack(max_overdue_age=TTL)
    expired = _scheduled(s, execute_at=OVERDUE)
    forged = replace(
        s["batch_plan_service"].plan("task-1", now=NOW), schedule_ids=("no-such-schedule", expired.schedule_id)
    )

    result = _execute(s, forged)

    assert [e.outcome for e in result.entries] == [BATCH_FAILED, BATCH_CLEANED]


def test_plan_for_another_task_and_bad_arguments_are_rejected():
    s = _stack()
    other = s["batch_plan_service"].plan("task-2", now=NOW)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupBatchError):
        s["batch_service"].execute("task-1", other, now=NOW)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupBatchError):
        s["batch_service"].execute("task-1", ["s1"], now=NOW)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupBatchError):
        s["batch_service"].execute("", now=NOW)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupBatchError):
        s["batch_service"].execute("task-1", now="soon")
