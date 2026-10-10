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
    DEGRADED,
    HEALTHY,
    SCHEDULED,
    DEFAULT_SCHEDULE_EXPIRATION_TTL,
    InvalidAgentTaskRecoveryScheduleReportingError,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
    LLMAgentTaskRecoveryPreflightScheduleExpirationService,
    LLMAgentTaskRecoveryPreflightScheduleHealthService,
    LLMAgentTaskRecoveryPreflightScheduleReportingService,
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


def _stack(with_expiration=False, dispatch_queue_service=None):
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
    health_service = LLMAgentTaskRecoveryPreflightScheduleHealthService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        recovery_service=recovery_service, expiration_service=expiration_service,
    )
    reporting_service = LLMAgentTaskRecoveryPreflightScheduleReportingService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        health_service=health_service, expiration_service=expiration_service,
    )
    return {
        "event_service": event_service,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "scheduling_service": scheduling_service,
        "dispatch_service": dispatch_service,
        "reporting_service": reporting_service,
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


# --- empty history --------------------------------------------------------------


def test_report_for_never_scheduled_task_is_empty():
    s = _stack()

    report = s["reporting_service"].report("never-scheduled", now=NOW)

    assert report.total_schedules == 0
    assert report.entries == ()
    assert report.status_counts == {}
    assert report.pending_count == 0
    assert report.dispatched_count == 0
    assert report.health_status == HEALTHY


def test_history_for_never_scheduled_task_is_empty():
    s = _stack()

    history = s["reporting_service"].history("never-scheduled", now=NOW)

    assert history.total_schedules == 0
    assert history.entries == ()


# --- mixed statuses --------------------------------------------------------------


def test_report_counts_mixed_statuses():
    s = _stack(dispatch_queue_service=_FakeQueueService())
    dispatched = _scheduled(s, task_id="task-1")
    s["dispatch_service"].dispatch("task-1", dispatched.schedule_id)

    pending = _scheduled(s, task_id="task-2")

    cancelled_source = _scheduled(s, task_id="task-3")
    s["scheduling_service"].cancel("task-3", cancelled_source.schedule_id, reason="operator cancelled")

    report_1 = s["reporting_service"].report("task-1", now=NOW)
    assert report_1.dispatched_count == 1
    assert report_1.pending_count == 0
    assert report_1.status_counts == {SCHEDULED: 1}

    report_2 = s["reporting_service"].report("task-2", now=NOW)
    assert report_2.pending_count == 1
    assert report_2.dispatched_count == 0

    report_3 = s["reporting_service"].report("task-3", now=NOW)
    assert report_3.status_counts == {CANCELLED: 1}
    assert report_3.health_status == HEALTHY


# --- failures / retries (via health issues) --------------------------------------------------------------


def test_report_surfaces_orphaned_dispatch_as_degraded():
    s = _stack()
    _scheduled(s)  # never dispatched, due -> orphaned per Commit #9/#10

    report = s["reporting_service"].report("task-1", now=NOW)

    assert report.health_status == DEGRADED
    entry = report.entries[0]
    assert any(issue.code == "orphaned_dispatch" for issue in entry.issues)


def test_report_tracks_expired_count_only_when_wired():
    ttl = DEFAULT_SCHEDULE_EXPIRATION_TTL
    s_untracked = _stack(with_expiration=False)
    _scheduled(s_untracked, execute_at=NOW - ttl - timedelta(minutes=1))
    report_untracked = s_untracked["reporting_service"].report("task-1", now=NOW)
    assert report_untracked.expired_count is None

    s_tracked = _stack(with_expiration=True)
    _scheduled(s_tracked, execute_at=NOW - ttl - timedelta(minutes=1))
    report_tracked = s_tracked["reporting_service"].report("task-1", now=NOW)
    assert report_tracked.expired_count == 1
    assert report_tracked.capacity_blocked_count is None
    assert report_tracked.retry_activity_count is None


# --- current-vs-historical reporting --------------------------------------------------------------


def test_history_preserves_cancelled_schedules_report_does_not_by_default():
    s = _stack()
    schedule = _scheduled(s)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="operator cancelled")

    history = s["reporting_service"].history("task-1", now=NOW)
    assert history.total_schedules == 1
    assert history.entries[0].status == CANCELLED
    assert history.entries[0].cancellation_reason == "operator cancelled"

    report = s["reporting_service"].report("task-1", now=NOW)
    assert report.total_schedules == 1  # still visible, but as a CURRENT cancelled entry, not omitted
    assert report.entries[0].status == CANCELLED
    assert report.health_status == HEALTHY  # a cleanly cancelled schedule is not itself a live problem


def test_history_is_chronological():
    s = _stack()
    first = _scheduled(s, task_id="task-1")
    s["scheduling_service"].cancel("task-1", first.schedule_id, reason="operator cancelled")

    history = s["reporting_service"].history("task-1", now=NOW)

    timestamps = [e.created_at for e in history.entries]
    assert timestamps == sorted(timestamps)


def test_scoped_report_for_single_schedule():
    s = _stack(dispatch_queue_service=_FakeQueueService())
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    report = s["reporting_service"].report("task-1", schedule_id=schedule.schedule_id, now=NOW)

    assert report.schedule_id == schedule.schedule_id
    assert report.total_schedules == 1
    assert report.entries[0].dispatched is True
    assert report.entries[0].queue_reference is not None


def test_report_entry_age_reflects_now():
    s = _stack()
    schedule = _scheduled(s)

    report = s["reporting_service"].report("task-1", now=schedule.created_at + timedelta(hours=3))

    assert report.entries[0].age == timedelta(hours=3)


def test_unknown_schedule_id_raises():
    s = _stack()
    _scheduled(s)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleReportingError):
        s["reporting_service"].report("task-1", schedule_id="does-not-exist", now=NOW)


def test_blank_task_id_rejected():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleReportingError):
        s["reporting_service"].report("", now=NOW)
