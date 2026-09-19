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
    InvalidAgentTaskRecoveryScheduleCleanupMaintenanceError,
    LLMAgentTaskRecoveryPreflightScheduleCleanupMaintenanceService,
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




def _maintenance(s):
    results = LLMAgentTaskRecoveryPreflightScheduleCleanupResultService()
    service = LLMAgentTaskRecoveryPreflightScheduleCleanupMaintenanceService(
        candidate_service=s["candidate_service"], result_service=results
    )
    return results, service


def _summarize(service, before=None):
    return service.summarize("task-1", now=NOW, before=before)


def test_empty_task_summary():
    _, service = _maintenance(_stack())

    summary = _summarize(service)

    assert (summary.current_candidates, summary.outstanding_count) == ((), 0)
    assert summary.latest_result is None
    assert (summary.latest_cleaned_count, summary.latest_skipped_count, summary.latest_failed_count) == (None,) * 3
    assert summary.last_maintenance_at is None
    assert (summary.historical_results, summary.retention_eligible, summary.retention_protected) == ((), (), ())
    assert summary.summarized_at == NOW


def test_missing_history_still_reports_outstanding_candidates_without_running_cleanup():
    s = _stack(max_overdue_age=TTL)
    expired_new, expired_old, invalidated = _mixed(s)
    _, service = _maintenance(s)

    summary = _summarize(service)

    assert [c.schedule_id for c in summary.current_candidates] == [c.schedule_id for c in s["candidate_service"].find("task-1", now=NOW)]
    assert summary.outstanding_count == 3
    assert summary.latest_result is None and summary.last_maintenance_at is None
    for schedule in (expired_new, expired_old, invalidated):
        assert s["scheduling_service"].get("task-1", schedule.schedule_id).status != CANCELLED


def test_normal_summary_after_a_recorded_cleanup():
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    results, service = _maintenance(s)
    record = results.record("task-1", _execute(s))

    summary = _summarize(service)

    assert (summary.current_candidates, summary.outstanding_count) == ((), 0)
    assert summary.latest_result.result_id == record.result_id
    assert summary.latest_result.is_current is True
    assert (summary.latest_cleaned_count, summary.latest_skipped_count, summary.latest_failed_count) == (3, 0, 0)
    assert summary.last_maintenance_at == NOW
    assert summary.historical_results == ()


def test_mixed_results_separate_current_candidates_from_history_and_retention():
    s = _stack(max_overdue_age=TTL)
    _, expired_old, _ = _mixed(s)
    failing = LLMAgentTaskRecoveryPreflightScheduleCleanupBatchService(
        plan_service=s["batch_plan_service"], cleanup_service=_FailingFor(s["cleanup_service"], [expired_old.schedule_id])
    )
    results, service = _maintenance(s)
    first = results.record("task-1", failing.execute("task-1", now=NOW))
    outstanding = _summarize(service)
    second = results.record("task-1", s["batch_service"].execute("task-1", now=NOW + timedelta(hours=1)))

    summary = _summarize(service, before=NOW + timedelta(minutes=30))

    assert [c.schedule_id for c in outstanding.current_candidates] == [expired_old.schedule_id]
    assert outstanding.latest_result.failed_count == 1 and outstanding.outstanding_count == 1
    assert summary.current_candidates == () and summary.outstanding_count == 0
    assert summary.latest_result.result_id == second.result_id
    assert (summary.latest_cleaned_count, summary.latest_failed_count) == (1, 0)
    assert summary.last_maintenance_at == NOW + timedelta(hours=1)
    assert summary.historical_results == ((first.result_id, NOW),)
    assert summary.retention_eligible == (first.result_id,)
    assert summary.retention_protected == ()


def test_summary_is_deterministic_read_only_and_never_applies_retention():
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    results, service = _maintenance(s)
    results.record("task-1", _execute(s))
    results.record("task-1", s["batch_service"].execute("task-1", now=NOW + timedelta(hours=1)))
    schedules, history = s["scheduling_service"].list("task-1"), results.history("task-1")

    first = _summarize(service, before=NOW + timedelta(days=1))

    assert first.retention_eligible
    assert first == _summarize(service, before=NOW + timedelta(days=1))
    assert s["scheduling_service"].list("task-1") == schedules
    assert results.history("task-1") == history


def test_invalid_arguments_are_rejected():
    _, service = _maintenance(_stack())
    for call in (
        lambda: service.summarize(""),
        lambda: service.summarize(None),
        lambda: service.summarize("task-1", now="soon"),
        lambda: service.summarize("task-1", before="yesterday"),
    ):
        with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupMaintenanceError):
            call()
