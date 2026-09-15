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
    INVALIDATED,
    SCHEDULED,
    InvalidAgentTaskRecoverySchedulingError,
    LLMAgentTaskRecoveryPreflightSchedulingService,
)


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


def _stack(readiness=None):
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
    validation_service = LLMAgentTaskRecoveryPreflightAuthorizationValidationService(
        authorization_service=authorization_service, preflight_store=preflight_store,
        invalidation_service=invalidation_service, freshness_service=freshness_service,
        approval_service=approval_service, evaluation_service=evaluation_service,
    )
    scheduling_service = LLMAgentTaskRecoveryPreflightSchedulingService(
        approval_service=approval_service, authorization_service=authorization_service,
        validation_service=validation_service,
    )
    return {
        "event_service": event_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "scheduling_service": scheduling_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _approved_preflight(s, task_id="task-1"):
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    return preflight


# --- valid scheduling --------------------------------------------------------------


def test_valid_scheduling():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    execute_at = datetime.now(timezone.utc) + timedelta(hours=1)

    schedule = s["scheduling_service"].schedule("task-1", preflight.preflight_id, execute_at=execute_at)

    assert schedule.status == SCHEDULED
    assert schedule.task_id == "task-1"
    assert schedule.preflight_id == preflight.preflight_id
    assert schedule.execute_at == execute_at
    assert schedule.authorization_id is not None
    fetched = s["scheduling_service"].get("task-1", schedule.schedule_id)
    assert fetched.status == SCHEDULED


def test_schedule_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoverySchedulingError):
        s["scheduling_service"].schedule("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoverySchedulingError):
        s["scheduling_service"].schedule("task-1", "")


def test_schedule_rejects_non_datetime_execute_at():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    with pytest.raises(InvalidAgentTaskRecoverySchedulingError):
        s["scheduling_service"].schedule("task-1", preflight.preflight_id, execute_at="tomorrow")


def test_schedule_is_idempotent():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)

    first = s["scheduling_service"].schedule("task-1", preflight.preflight_id)
    second = s["scheduling_service"].schedule("task-1", preflight.preflight_id)

    assert first.schedule_id == second.schedule_id


# --- rejected/stale preflights --------------------------------------------------------------


def test_rejected_preflight_cannot_be_scheduled():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)
    s["approval_service"].reject("task-1", preflight.preflight_id, actor="bob", reason="no")

    with pytest.raises(InvalidAgentTaskRecoverySchedulingError):
        s["scheduling_service"].schedule("task-1", preflight.preflight_id)


def test_never_approved_preflight_cannot_be_scheduled():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))

    with pytest.raises(InvalidAgentTaskRecoverySchedulingError):
        s["scheduling_service"].schedule("task-1", preflight.preflight_id)


def test_invalidated_preflight_cannot_be_scheduled():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    with pytest.raises(InvalidAgentTaskRecoverySchedulingError):
        s["scheduling_service"].schedule("task-1", preflight.preflight_id)


# --- authorization failures --------------------------------------------------------------


def test_policy_blocked_preflight_cannot_be_scheduled():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    s["readiness"].set(policy_passed=False)

    with pytest.raises(InvalidAgentTaskRecoverySchedulingError):
        s["scheduling_service"].schedule("task-1", preflight.preflight_id)


# --- exact task/preflight binding --------------------------------------------------------------


def test_schedule_bound_to_exact_task_and_preflight():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    schedule = s["scheduling_service"].schedule("task-1", preflight.preflight_id)

    assert s["scheduling_service"].get("task-2", schedule.schedule_id) is None
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).preflight_id == preflight.preflight_id


# --- cancellation/idempotency --------------------------------------------------------------


def test_cancellation_and_idempotency():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    schedule = s["scheduling_service"].schedule("task-1", preflight.preflight_id)

    cancelled = s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")
    assert cancelled.status == CANCELLED
    assert cancelled.cancellation_reason == "no longer needed"

    again = s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="different reason")
    assert again.cancellation_reason == "no longer needed"


def test_cancel_unknown_schedule_raises():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoverySchedulingError):
        s["scheduling_service"].cancel("task-1", "never-existed")


# --- persistence/history --------------------------------------------------------------


def test_persistence_history_lists_all_schedules():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    schedule = s["scheduling_service"].schedule("task-1", preflight.preflight_id)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id)

    history = s["scheduling_service"].list("task-1")
    assert len(history) == 1
    assert history[0].status == CANCELLED


def test_get_missing_schedule_returns_none():
    s = _stack()
    assert s["scheduling_service"].get("task-1", "never-existed") is None
    assert s["scheduling_service"].list("task-1") == []


# --- schedule invalidation after preflight changes --------------------------------------------------------------


def test_schedule_becomes_invalidated_after_authorization_is_revoked():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    schedule = s["scheduling_service"].schedule("task-1", preflight.preflight_id)

    s["authorization_service"].revoke("task-1", schedule.authorization_id, reason="revoked externally")

    effective = s["scheduling_service"].get("task-1", schedule.schedule_id)
    assert effective.status == INVALIDATED

    # The underlying stored record is never rewritten:
    raw = s["scheduling_service"]._store.get(schedule.schedule_id)
    assert raw.status == SCHEDULED


def test_schedule_becomes_invalidated_after_task_invalidation():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    schedule = s["scheduling_service"].schedule("task-1", preflight.preflight_id)

    s["invalidation_service"].invalidate("task-1", reason="found a real problem")

    effective_list = s["scheduling_service"].list("task-1")
    assert effective_list[0].status == INVALIDATED
