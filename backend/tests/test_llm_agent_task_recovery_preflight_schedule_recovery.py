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
    BLOCKED,
    CANCELLED,
    COMPLETE_HANDOFF,
    NO_ACTION_REQUIRED,
    REDISPATCH,
    DEFAULT_SCHEDULE_EXPIRATION_TTL,
    InvalidAgentTaskRecoveryScheduleRecoveryError,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
    LLMAgentTaskRecoveryPreflightScheduleExpirationService,
    LLMAgentTaskRecoveryPreflightScheduleReconciliationService,
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
    def __init__(self):
        self.enqueued = []

    def enqueue(self, task_id):
        self.enqueued.append(task_id)
        return type("Entry", (), {"task_id": task_id})()


class _BrokenQueueService:
    def enqueue(self, task_id):
        raise RuntimeError("queue is unavailable")


def _stack(readiness=None, dispatch_queue_service=None, recovery_queue_service=None, with_expiration=False):
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
    dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        scheduling_service=scheduling_service, validation_service=schedule_validation_service,
        queue_service=dispatch_queue_service,
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightScheduleReconciliationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
        dispatch_service=dispatch_service,
    )
    expiration_service = None
    if with_expiration:
        expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(
            scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        )
    recovery_service = LLMAgentTaskRecoveryPreflightScheduleRecoveryService(
        scheduling_service=scheduling_service, dispatch_service=dispatch_service,
        validation_service=schedule_validation_service, reconciliation_service=reconciliation_service,
        expiration_service=expiration_service, queue_service=recovery_queue_service,
    )
    return {
        "event_service": event_service,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "scheduling_service": scheduling_service,
        "dispatch_service": dispatch_service,
        "recovery_service": recovery_service,
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


# --- orphan detection / find_recoverable --------------------------------------------------------------


def test_find_recoverable_returns_only_orphaned_schedules():
    s = _stack()
    orphaned = _scheduled(s, task_id="task-1")
    _scheduled(s, task_id="task-2")
    s["dispatch_service"].dispatch("task-2", s["scheduling_service"].list("task-2")[0].schedule_id)

    recoverable = s["recovery_service"].find_recoverable("task-1", now=NOW)
    assert {r.schedule_id for r in recoverable} == {orphaned.schedule_id}

    recoverable_2 = s["recovery_service"].find_recoverable("task-2", now=NOW)
    assert recoverable_2 == ()


# --- recoverable vs unrecoverable schedules --------------------------------------------------------------


def test_never_dispatched_due_schedule_is_recoverable():
    s = _stack()
    schedule = _scheduled(s)

    plan = s["recovery_service"].plan_recovery("task-1", schedule.schedule_id, now=NOW)

    assert plan.recoverable is True
    assert plan.action == REDISPATCH


def test_fully_dispatched_schedule_is_not_recoverable():
    s = _stack(dispatch_queue_service=_FakeQueueService())
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    plan = s["recovery_service"].plan_recovery("task-1", schedule.schedule_id, now=NOW)

    assert plan.recoverable is False
    assert plan.action == NO_ACTION_REQUIRED


def test_not_yet_due_schedule_is_not_recoverable():
    s = _stack()
    schedule = _scheduled(s, execute_at=NOW + timedelta(hours=1))

    plan = s["recovery_service"].plan_recovery("task-1", schedule.schedule_id, now=NOW)

    assert plan.recoverable is False
    assert plan.action == NO_ACTION_REQUIRED


# --- interrupted dispatch (queue handoff missing) --------------------------------------------------------------


def test_interrupted_dispatch_completes_handoff():
    fake_queue = _FakeQueueService()
    s = _stack(recovery_queue_service=fake_queue)  # dispatch_service itself has NO queue_service
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)  # persisted with queue_reference=None

    plan = s["recovery_service"].plan_recovery("task-1", schedule.schedule_id, now=NOW)
    assert plan.action == COMPLETE_HANDOFF

    result = s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW)

    assert result.action_taken == COMPLETE_HANDOFF
    assert result.repaired is True
    assert "task-1" in fake_queue.enqueued


def test_missing_queue_service_blocks_handoff_completion():
    s = _stack()  # no recovery_queue_service at all
    schedule = _scheduled(s)
    s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleRecoveryError):
        s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW)


# --- duplicate-prevention / idempotency --------------------------------------------------------------


def test_repeated_recover_never_creates_duplicate_dispatch():
    fake_queue = _FakeQueueService()
    s = _stack(dispatch_queue_service=fake_queue)
    schedule = _scheduled(s)

    first = s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW)
    second = s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW + timedelta(minutes=5))
    third = s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW + timedelta(minutes=10))

    assert first.repaired is True
    assert first.action_taken == REDISPATCH
    assert second.repaired is False
    assert third.repaired is False
    assert len(s["dispatch_service"].list("task-1")) == 1


# --- expired/cancelled schedules --------------------------------------------------------------


def test_cancelled_schedule_is_never_recovered():
    s = _stack()
    schedule = _scheduled(s)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="operator cancelled")

    result = s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW)

    assert result.repaired is False
    assert s["dispatch_service"].list("task-1") == []


def test_revoked_schedule_is_never_recovered():
    s = _stack()
    schedule = _scheduled(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    result = s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW)

    assert result.repaired is False
    assert s["dispatch_service"].list("task-1") == []


def test_expired_schedule_is_never_recovered():
    ttl = DEFAULT_SCHEDULE_EXPIRATION_TTL
    s = _stack(with_expiration=True)
    schedule = _scheduled(s, execute_at=NOW - ttl - timedelta(minutes=1))

    plan = s["recovery_service"].plan_recovery("task-1", schedule.schedule_id, now=NOW)
    assert plan.recoverable is False

    result = s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW)
    assert result.repaired is False
    assert s["dispatch_service"].list("task-1") == []


# --- successful repair --------------------------------------------------------------


def test_successful_repair_returns_dispatch():
    s = _stack()
    schedule = _scheduled(s)

    result = s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW)

    assert result.repaired is True
    assert result.dispatch is not None
    assert result.dispatch.schedule_id == schedule.schedule_id


# --- ambiguous state --------------------------------------------------------------


def test_ambiguous_dispatch_history_is_blocked():
    s = _stack()
    schedule = _scheduled(s)
    d1 = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    # Directly corrupt the store with a second dispatch record for the
    # same schedule_id -- something Commit #3's own idempotent dispatch()
    # should never itself produce, simulating an inconsistent/orphaned
    # state this class must refuse to guess about.
    corrupted = replace(d1, dispatch_id="dispatch-2")
    s["dispatch_service"]._store.save(corrupted)

    plan = s["recovery_service"].plan_recovery("task-1", schedule.schedule_id, now=NOW)
    assert plan.action == BLOCKED

    with pytest.raises(InvalidAgentTaskRecoveryScheduleRecoveryError):
        s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW)


# --- preservation of history --------------------------------------------------------------


def test_recovery_preserves_original_schedule():
    s = _stack()
    schedule = _scheduled(s)

    s["recovery_service"].recover("task-1", schedule.schedule_id, now=NOW)

    after = s["scheduling_service"].get("task-1", schedule.schedule_id)
    assert after.schedule_id == schedule.schedule_id
    assert after.preflight_id == schedule.preflight_id
    assert after.created_at == schedule.created_at
    assert after.execute_at == schedule.execute_at
    assert after.status == schedule.status


def test_unknown_schedule_id_raises():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleRecoveryError):
        s["recovery_service"].plan_recovery("task-1", "does-not-exist", now=NOW)
