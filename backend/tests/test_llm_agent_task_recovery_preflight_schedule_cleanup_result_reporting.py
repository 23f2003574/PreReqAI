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
    InvalidAgentTaskRecoveryScheduleCleanupResultReportingError,
    LLMAgentTaskRecoveryPreflightScheduleCleanupResultReportingService,
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
    return results, LLMAgentTaskRecoveryPreflightScheduleCleanupResultReportingService(result_service=results)


def test_successful_result_report():
    s = _stack(max_overdue_age=TTL)
    expired_new, expired_old, invalidated = _mixed(s)
    results, reporting = _services()
    record = results.record("task-1", _execute(s))

    report = reporting.report("task-1")

    assert report.result_id == record.result_id
    assert report.executed_at == NOW
    assert report.recorded_at == record.recorded_at
    assert report.total_processed == 3
    assert (report.cleaned_count, report.skipped_count, report.failed_count) == (3, 0, 0)
    assert [(e.schedule_id, e.outcome, e.reason) for e in report.entries] == [
        (invalidated.schedule_id, BATCH_CLEANED, "invalidated"),
        (expired_old.schedule_id, BATCH_CLEANED, "expired"),
        (expired_new.schedule_id, BATCH_CLEANED, "expired"),
    ]
    assert report.failure_summary == ()
    assert report.is_current is True
    assert report.current_result_id == record.result_id
    assert report.historical_results == ()


def test_partial_failure_report_summarizes_failures():
    s = _stack(max_overdue_age=TTL)
    _, expired_old, _ = _mixed(s)
    service = LLMAgentTaskRecoveryPreflightScheduleCleanupBatchService(
        plan_service=s["batch_plan_service"], cleanup_service=_FailingFor(s["cleanup_service"], [expired_old.schedule_id])
    )
    results, reporting = _services()
    results.record("task-1", service.execute("task-1", now=NOW))

    report = reporting.report("task-1")

    assert (report.cleaned_count, report.failed_count, report.total_processed) == (2, 1, 3)
    assert report.failure_summary == ((expired_old.schedule_id, "boom"),)


def test_empty_result_report():
    results, reporting = _services()
    results.record("task-1", _stack()["batch_service"].execute("task-1", now=NOW))

    report = reporting.report("task-1")

    assert (report.total_processed, report.entries, report.failure_summary) == (0, (), ())
    assert (report.cleaned_count, report.skipped_count, report.failed_count) == (0, 0, 0)


def test_historical_result_is_distinguished_from_current():
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    results, reporting = _services()
    older = results.record("task-1", s["batch_service"].execute("task-1", now=NOW))
    newer = results.record("task-1", s["batch_service"].execute("task-1", now=NOW + timedelta(hours=1)))

    current = reporting.report("task-1")
    historical = reporting.report("task-1", older.result_id)

    assert current.result_id == newer.result_id and current.is_current is True
    assert current.historical_results == ((older.result_id, NOW),)
    assert historical.result_id == older.result_id and historical.is_current is False
    assert historical.current_result_id == newer.result_id
    assert historical.cleaned_count == 3
    assert historical.historical_results == ((newer.result_id, NOW + timedelta(hours=1)),)
    assert reporting.report("task-1", newer.result_id) == current


def test_report_is_deterministic_and_read_only():
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    results, reporting = _services()
    results.record("task-1", _execute(s))
    schedules, history = s["scheduling_service"].list("task-1"), results.history("task-1")

    assert reporting.report("task-1") == reporting.report("task-1")
    assert s["scheduling_service"].list("task-1") == schedules
    assert results.history("task-1") == history


def test_missing_results_and_bad_arguments_are_rejected():
    results, reporting = _services()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupResultReportingError):
        reporting.report("task-1")
    results.record("task-1", _stack()["batch_service"].execute("task-1", now=NOW))
    for call in (
        lambda: reporting.report("task-1", "no-such-result"),
        lambda: reporting.report("task-2"),
        lambda: reporting.report(""),
        lambda: reporting.report("task-1", ""),
    ):
        with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupResultReportingError):
            call()
