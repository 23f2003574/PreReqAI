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
    InvalidAgentTaskRecoveryScheduleCleanupCandidateError,
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
    return {
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


def _find(s, now=NOW):
    return s["candidate_service"].find("task-1", now=now)


def test_empty_task_has_no_candidates():
    assert _stack()["candidate_service"].find("no-such-task", now=NOW) == ()


def test_only_active_schedules_yield_no_candidates():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW + timedelta(hours=1))

    assert _find(s) == ()
    assert s["candidate_service"].is_candidate("task-1", schedule.schedule_id, now=NOW) is False


def test_expired_candidate_carries_id_state_reason_and_timestamps():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=OVERDUE)

    (candidate,) = _find(s)

    assert candidate.schedule_id == schedule.schedule_id
    assert candidate.preflight_id == schedule.preflight_id
    assert candidate.status == "scheduled"
    assert candidate.reason == "expired"
    assert candidate.created_at == schedule.created_at
    assert candidate.eligible_since == OVERDUE + TTL
    assert s["candidate_service"].is_candidate("task-1", schedule.schedule_id, now=NOW) is True


def test_invalidated_candidate_has_no_eligible_since():
    s = _stack(max_overdue_age=TTL)
    schedule = _scheduled(s, execute_at=NOW + timedelta(hours=1))
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    (candidate,) = _find(s)

    assert (candidate.schedule_id, candidate.status, candidate.reason) == (
        schedule.schedule_id, "invalidated", "invalidated",
    )
    assert candidate.eligible_since is None


def test_cancelled_and_dispatched_schedules_are_not_candidates():
    s = _stack(max_overdue_age=TTL)
    cancelled = _scheduled(s, execute_at=OVERDUE)
    s["scheduling_service"].cancel("task-1", cancelled.schedule_id, reason="manual")

    assert _find(s) == ()
    assert s["candidate_service"].is_candidate("task-1", cancelled.schedule_id, now=NOW) is False

    s2 = _stack(max_overdue_age=TTL)
    dispatched = _scheduled(s2, execute_at=NOW - timedelta(hours=1))
    s2["dispatch_service"].dispatch("task-1", dispatched.schedule_id)

    assert _find(s2, now=NOW + TTL * 2) == ()
    assert s2["candidate_service"].is_candidate("task-1", dispatched.schedule_id, now=NOW + TTL * 2) is False


def test_mixed_schedules_yield_exactly_what_cleanup_cleans_in_order():
    s = _stack(max_overdue_age=TTL)
    expired = _scheduled(s, execute_at=OVERDUE)
    active = _extra(s, expired, NOW + timedelta(hours=1), "p1")
    dispatched = _extra(s, expired, NOW - timedelta(hours=1), "p2")
    s["dispatch_service"].dispatch("task-1", dispatched.schedule_id)
    cancelled = _extra(s, expired, OVERDUE, "p3")
    s["scheduling_service"].cancel("task-1", cancelled.schedule_id, reason="manual")

    candidates = _find(s)

    assert [c.schedule_id for c in candidates] == [expired.schedule_id]
    for schedule in (active, dispatched, cancelled):
        assert s["candidate_service"].is_candidate("task-1", schedule.schedule_id, now=NOW) is False
    result = s["cleanup_service"].cleanup("task-1", now=NOW)
    assert tuple((c.schedule_id, c.reason) for c in candidates) == result.cleaned_reasons
    assert _find(s) == ()


def test_several_candidates_are_ordered_by_creation():
    s = _stack(max_overdue_age=TTL)
    first = _scheduled(s, execute_at=OVERDUE)
    second = _extra(s, first, OVERDUE, "p1")
    third = _extra(s, first, OVERDUE, "p2")

    assert [c.schedule_id for c in _find(s)] == [first.schedule_id, second.schedule_id, third.schedule_id]


def test_find_is_read_only_and_deterministic():
    s = _stack(max_overdue_age=TTL)
    _scheduled(s, execute_at=OVERDUE)
    _scheduled(s, execute_at=NOW + timedelta(hours=1))
    before = (s["scheduling_service"].list("task-1"), s["dispatch_service"].list("task-1"))

    first, second = _find(s), _find(s)

    assert first and first == second
    assert (s["scheduling_service"].list("task-1"), s["dispatch_service"].list("task-1")) == before


def test_unknown_schedule_is_not_a_candidate():
    assert _stack()["candidate_service"].is_candidate("task-1", "no-such-schedule", now=NOW) is False


@pytest.mark.parametrize("task_id", [None, "", 5])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupCandidateError):
        _stack()["candidate_service"].find(task_id)


@pytest.mark.parametrize("schedule_id", [None, ""])
def test_invalid_schedule_id_is_rejected(schedule_id):
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupCandidateError):
        _stack()["candidate_service"].is_candidate("task-1", schedule_id)


def test_invalid_now_is_rejected():
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupCandidateError):
        _stack()["candidate_service"].find("task-1", now="soon")

