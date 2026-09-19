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
    InvalidAgentTaskRecoveryScheduleCleanupOrderingError,
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
    return {
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


def _order(s, candidates=None):
    return s["ordering_service"].order("task-1", candidates, now=NOW)


def _ids(candidates):
    return [c.schedule_id for c in candidates]


def test_empty_candidates_order_to_empty():
    s = _stack()

    assert s["ordering_service"].order("no-such-task", now=NOW) == ()
    assert _order(s, []) == ()


def test_orders_expired_candidates_oldest_deadline_first():
    s = _stack(max_overdue_age=TTL)
    newer = _scheduled(s, execute_at=OVERDUE - timedelta(minutes=30))
    older = _extra(s, newer, OVERDUE - timedelta(hours=2), "p1")
    oldest = _extra(s, newer, OVERDUE - timedelta(hours=5), "p2")

    assert _ids(_order(s)) == [oldest.schedule_id, older.schedule_id, newer.schedule_id]


def test_result_does_not_depend_on_input_order():
    s = _stack(max_overdue_age=TTL)
    base = _scheduled(s, execute_at=OVERDUE)
    _extra(s, base, OVERDUE - timedelta(hours=2), "p1")
    _extra(s, base, OVERDUE - timedelta(hours=5), "p2")
    found = s["candidate_service"].find("task-1", now=NOW)

    assert _order(s, list(found)) == _order(s, list(reversed(found))) == _order(s)


def test_ties_break_on_created_at_then_schedule_id():
    s = _stack(max_overdue_age=TTL)
    first = _scheduled(s, execute_at=OVERDUE)
    second = _extra(s, first, OVERDUE, "p1")
    third = replace(second, schedule_id="0" + second.schedule_id[1:], preflight_id="p2")
    s["scheduling_service"]._store.save(third)

    ordered = _order(s)

    assert _ids(ordered) == [first.schedule_id, *sorted([second.schedule_id, third.schedule_id])]
    assert [c.created_at for c in ordered][1] == [c.created_at for c in ordered][2]


def test_invalidated_precedes_expired():
    s = _stack(max_overdue_age=TTL)
    expired = _scheduled(s, execute_at=OVERDUE)
    invalidated = _extra(s, expired, NOW + timedelta(hours=1), "p1")
    invalidated = s["scheduling_service"]._store.save(replace(invalidated, authorization_id="no-such-authorization"))
    assert s["scheduling_service"].get("task-1", invalidated.schedule_id).status == "invalidated"

    assert _ids(_order(s)) == [invalidated.schedule_id, expired.schedule_id]


def test_active_schedules_are_never_ordered_even_when_supplied():
    s = _stack(max_overdue_age=TTL)
    expired = _scheduled(s, execute_at=OVERDUE)
    active = _extra(s, expired, NOW + timedelta(hours=1), "p1")
    (candidate,) = s["candidate_service"].find("task-1", now=NOW)
    fake_active = replace(candidate, schedule_id=active.schedule_id)

    assert _ids(_order(s, [fake_active, candidate])) == [expired.schedule_id]


def test_stale_candidate_dropped_once_cleaned_and_other_tasks_ignored():
    s = _stack(max_overdue_age=TTL)
    _scheduled(s, execute_at=OVERDUE)
    (candidate,) = s["candidate_service"].find("task-1", now=NOW)

    assert _order(s, [candidate, candidate]) == (candidate,)
    assert s["ordering_service"].order("task-2", [candidate], now=NOW) == ()
    s["cleanup_service"].cleanup("task-1", now=NOW)
    assert _order(s, [candidate]) == ()


def test_ordering_is_read_only_and_deterministic():
    s = _stack(max_overdue_age=TTL)
    base = _scheduled(s, execute_at=OVERDUE)
    _extra(s, base, NOW + timedelta(hours=1), "p1")
    before = s["scheduling_service"].list("task-1")

    assert _order(s) == _order(s)
    assert s["scheduling_service"].list("task-1") == before


@pytest.mark.parametrize("task_id", [None, "", 5])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupOrderingError):
        _stack()["ordering_service"].order(task_id)


def test_non_candidates_and_bad_now_are_rejected():
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupOrderingError):
        _stack()["ordering_service"].order("task-1", ["s1"])
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupOrderingError):
        _stack()["ordering_service"].order("task-1", now="soon")
