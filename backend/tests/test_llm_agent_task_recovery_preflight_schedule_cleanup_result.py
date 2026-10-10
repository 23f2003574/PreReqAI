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
    InvalidAgentTaskRecoveryScheduleCleanupResultError,
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




@pytest.fixture(params=["memory", "json"])
def result_service(request, tmp_path):
    if request.param == "memory":
        store = InMemoryAgentTaskRecoveryScheduleCleanupResultStore()
    else:
        store = JsonAgentTaskRecoveryScheduleCleanupResultStore(tmp_path / "results.json")
    return LLMAgentTaskRecoveryPreflightScheduleCleanupResultService(store=store)


def test_successful_batch_is_recorded_and_linked_to_processed_schedules(result_service):
    s = _stack(max_overdue_age=TTL)
    expired_new, expired_old, invalidated = _mixed(s)
    batch = _execute(s)

    record = result_service.record("task-1", batch)

    assert (record.cleaned_count, record.skipped_count, record.failed_count) == (3, 0, 0)
    assert record.schedule_ids == (invalidated.schedule_id, expired_old.schedule_id, expired_new.schedule_id)
    assert record.entries == batch.entries
    assert record.executed_at == NOW
    assert result_service.get("task-1", record.result_id) == record


def test_partial_failure_preserves_failure_reason_and_timestamps(result_service):
    s = _stack(max_overdue_age=TTL)
    _, expired_old, _ = _mixed(s)
    service = LLMAgentTaskRecoveryPreflightScheduleCleanupBatchService(
        plan_service=s["batch_plan_service"], cleanup_service=_FailingFor(s["cleanup_service"], [expired_old.schedule_id])
    )
    batch = service.execute("task-1", now=NOW)

    record = result_service.record("task-1", batch)
    reloaded = result_service.get("task-1", record.result_id)

    assert (reloaded.cleaned_count, reloaded.failed_count) == (2, 1)
    failed = [e for e in reloaded.entries if e.outcome == BATCH_FAILED]
    assert [(e.schedule_id, e.error) for e in failed] == [(expired_old.schedule_id, "boom")]
    assert reloaded.executed_at == NOW
    assert reloaded.recorded_at >= NOW


def test_empty_batch_is_recorded(result_service):
    batch = _stack()["batch_service"].execute("task-1", now=NOW)

    record = result_service.record("task-1", batch)

    assert (record.entries, record.schedule_ids) == ((), ())
    assert (record.cleaned_count, record.skipped_count, record.failed_count) == (0, 0, 0)
    assert len(result_service.history("task-1")) == 1


def test_recording_the_same_batch_twice_is_idempotent(result_service):
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    batch = _execute(s)

    first = result_service.record("task-1", batch)
    second = result_service.record("task-1", batch)

    assert second == first
    assert result_service.history("task-1") == (first,)


def test_history_is_append_only_and_ordered_oldest_run_first(result_service):
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    first_batch = s["batch_service"].execute("task-1", now=NOW)
    second_batch = s["batch_service"].execute("task-1", now=NOW + timedelta(hours=1))
    first = result_service.record("task-1", second_batch)
    second = result_service.record("task-1", first_batch)

    assert first.result_id != second.result_id
    assert result_service.history("task-1") == (second, first)
    assert second.cleaned_count == 3 and first.cleaned_count == 0


def test_history_and_get_are_scoped_per_task_and_read_only(result_service):
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    record = result_service.record("task-1", _execute(s))
    before = s["scheduling_service"].list("task-1")

    assert result_service.history("task-2") == ()
    assert result_service.get("task-2", record.result_id) is None
    assert result_service.get("task-1", "no-such-result") is None
    assert result_service.history("task-1") == (record,)
    assert s["scheduling_service"].list("task-1") == before


def test_json_store_round_trips_records_across_service_instances(tmp_path):
    path = tmp_path / "results.json"
    s = _stack(max_overdue_age=TTL)
    _mixed(s)
    written = LLMAgentTaskRecoveryPreflightScheduleCleanupResultService(
        store=JsonAgentTaskRecoveryScheduleCleanupResultStore(path)
    ).record("task-1", _execute(s))

    reread = LLMAgentTaskRecoveryPreflightScheduleCleanupResultService(
        store=JsonAgentTaskRecoveryScheduleCleanupResultStore(path)
    )

    assert reread.history("task-1") == (written,)


def test_invalid_arguments_are_rejected(result_service):
    batch = _stack()["batch_service"].execute("task-1", now=NOW)
    for call in (
        lambda: result_service.record("", batch),
        lambda: result_service.record("task-1", {"cleaned": 1}),
        lambda: result_service.record("task-2", batch),
        lambda: result_service.get("task-1", ""),
        lambda: result_service.get("", "r"),
        lambda: result_service.history(None),
    ):
        with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupResultError):
            call()
