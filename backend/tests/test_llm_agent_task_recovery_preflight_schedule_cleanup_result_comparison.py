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
    InMemoryAgentTaskRecoveryScheduleCleanupResultStore,
    InvalidAgentTaskRecoveryScheduleCleanupResultComparisonError,
    LLMAgentTaskRecoveryPreflightScheduleCleanupResultComparisonService,
    JsonAgentTaskRecoveryScheduleCleanupResultStore,
    LLMAgentTaskRecoveryPreflightScheduleCleanupResultService,
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




def _services():
    results = LLMAgentTaskRecoveryPreflightScheduleCleanupResultService()
    return results, LLMAgentTaskRecoveryPreflightScheduleCleanupResultComparisonService(result_service=results)


def _failed_then_retried():
    """First run: expired_old fails (2 cleaned, 1 failed). Second run: it succeeds."""
    s = _stack(max_overdue_age=TTL)
    invalidated_ids = _mixed(s)
    expired_new, expired_old, invalidated = invalidated_ids
    failing = LLMAgentTaskRecoveryPreflightScheduleCleanupBatchService(
        plan_service=s["batch_plan_service"], cleanup_service=_FailingFor(s["cleanup_service"], [expired_old.schedule_id])
    )
    results, comparison = _services()
    first = results.record("task-1", failing.execute("task-1", now=NOW))
    second = results.record("task-1", s["batch_service"].execute("task-1", now=NOW + timedelta(hours=1)))
    return comparison, first, second, invalidated, expired_old, expired_new


def test_identical_result_compares_unchanged():
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    results, comparison = _services()
    record = results.record("task-1", _execute(s))

    result = comparison.compare("task-1", record.result_id, record.result_id)

    assert result.changed is False
    assert (result.appeared, result.disappeared, result.outcome_changes) == ((), (), ())
    assert (result.newly_failing, result.newly_cleaned) == ((), ())
    assert all(before == after for _, before, after in result.count_changes)


def test_two_empty_results_with_different_ids_compare_unchanged():
    results, comparison = _services()
    empty = _stack()["batch_service"]
    first = results.record("task-1", empty.execute("task-1", now=NOW))
    second = results.record("task-1", empty.execute("task-1", now=NOW + timedelta(hours=1)))

    result = comparison.compare("task-1", first.result_id, second.result_id)

    assert first.result_id != second.result_id
    assert result.changed is False


def test_retry_after_failure_shows_changes_and_newly_cleaned():
    comparison, first, second, invalidated, expired_old, expired_new = _failed_then_retried()

    result = comparison.compare("task-1", first.result_id, second.result_id)

    assert result.changed is True
    assert result.count_changes == (("processed", 3, 1), ("cleaned", 2, 1), ("skipped", 0, 0), ("failed", 1, 0))
    assert result.disappeared == (invalidated.schedule_id, expired_new.schedule_id)
    assert result.appeared == ()
    (before, after), = result.outcome_changes
    assert (before.schedule_id, before.outcome, before.error) == (expired_old.schedule_id, BATCH_FAILED, "boom")
    assert (after.schedule_id, after.outcome, after.reason) == (expired_old.schedule_id, BATCH_CLEANED, "expired")
    assert result.newly_cleaned == (expired_old.schedule_id,)
    assert result.newly_failing == ()


def test_reverse_order_shows_newly_failing_and_appeared_schedules():
    comparison, first, second, invalidated, expired_old, expired_new = _failed_then_retried()

    result = comparison.compare("task-1", second.result_id, first.result_id)

    assert result.appeared == (invalidated.schedule_id, expired_new.schedule_id)
    assert result.disappeared == ()
    assert result.newly_failing == (expired_old.schedule_id,)
    assert result.newly_cleaned == (invalidated.schedule_id, expired_new.schedule_id)
    (before, after), = result.outcome_changes
    assert (before.outcome, after.outcome) == (BATCH_CLEANED, BATCH_FAILED)


def test_empty_versus_populated_result():
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    results, comparison = _services()
    populated = results.record("task-1", _execute(s, s["batch_plan_service"].plan("task-1", now=NOW)))
    empty = results.record("task-1", s["batch_service"].execute("task-1", now=NOW + timedelta(hours=1)))

    result = comparison.compare("task-1", populated.result_id, empty.result_id)

    assert result.changed is True
    assert result.disappeared == populated.schedule_ids
    assert result.count_changes[0] == ("processed", 3, 0)
    assert (result.appeared, result.newly_cleaned, result.newly_failing) == ((), (), ())


def test_comparison_is_deterministic_and_read_only():
    comparison, first, second, *_ = _failed_then_retried()
    results = comparison._result_service
    history = results.history("task-1")

    assert comparison.compare("task-1", first.result_id, second.result_id) == comparison.compare(
        "task-1", first.result_id, second.result_id
    )
    assert results.history("task-1") == history


def test_missing_results_and_bad_arguments_are_rejected():
    results, comparison = _services()
    record = results.record("task-1", _stack()["batch_service"].execute("task-1", now=NOW))
    for call in (
        lambda: comparison.compare("task-1", record.result_id, "no-such-result"),
        lambda: comparison.compare("task-1", "no-such-result", record.result_id),
        lambda: comparison.compare("task-2", record.result_id, record.result_id),
        lambda: comparison.compare("", record.result_id, record.result_id),
        lambda: comparison.compare("task-1", None, record.result_id),
        lambda: comparison.compare("task-1", record.result_id, ""),
    ):
        with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupResultComparisonError):
            call()
