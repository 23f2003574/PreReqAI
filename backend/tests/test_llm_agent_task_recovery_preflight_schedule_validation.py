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
    InvalidAgentTaskRecoveryScheduleValidationError,
    LLMAgentTaskRecoveryPreflightSchedulingService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
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
    return {
        "event_service": event_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "scheduling_service": scheduling_service,
        "schedule_validation_service": schedule_validation_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _scheduled(s, task_id="task-1", execute_at=None):
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    schedule = s["scheduling_service"].schedule(task_id, preflight.preflight_id, execute_at=execute_at)
    return preflight, schedule


# --- valid path --------------------------------------------------------------


def test_valid_schedule_is_executable():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)

    result = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)

    assert result.valid is True
    assert result.blocking_reasons == ()
    assert result.preflight_id == preflight.preflight_id
    assert s["schedule_validation_service"].is_executable("task-1", schedule.schedule_id) is True


def test_validate_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleValidationError):
        s["schedule_validation_service"].validate("", "id")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleValidationError):
        s["schedule_validation_service"].validate("task-1", "")


# --- missing --------------------------------------------------------------


def test_missing_schedule_is_invalid():
    s = _stack()
    result = s["schedule_validation_service"].validate("task-1", "never-existed")
    assert result.valid is False
    assert result.preflight_id is None


def test_schedule_from_wrong_task_is_missing():
    s = _stack()
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s, task_id="task-1")

    result = s["schedule_validation_service"].validate("task-2", schedule.schedule_id)
    assert result.valid is False


# --- cancelled --------------------------------------------------------------


def test_cancelled_schedule_is_invalid():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")

    result = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert result.valid is False
    assert any("cancelled" in r for r in result.blocking_reasons)


# --- revoked/invalidated/superseded/policy-blocked (via authorization validation reuse) -----------------------


def test_revoked_authorization_makes_schedule_invalid():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["authorization_service"].revoke("task-1", schedule.authorization_id, reason="revoked externally")

    result = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert result.valid is False
    assert any("revoked" in r for r in result.blocking_reasons)


def test_invalidated_preflight_makes_schedule_invalid():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    result = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert result.valid is False
    assert any("invalidated" in r for r in result.blocking_reasons)


def test_policy_blocked_makes_schedule_invalid():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)
    s["readiness"].set(policy_passed=False)

    result = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert result.valid is False
    assert any("recovery guard/policy evaluation" in r for r in result.blocking_reasons)


# --- execution window not reached --------------------------------------------------------------


def test_future_execution_window_is_not_yet_executable():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s, execute_at=datetime.now(timezone.utc) + timedelta(hours=1))

    result = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert result.valid is False
    assert any("execution window has not been reached" in r for r in result.blocking_reasons)


def test_past_execution_window_is_executable():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s, execute_at=datetime.now(timezone.utc) - timedelta(hours=1))

    result = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert result.valid is True


def test_no_execute_at_is_always_within_window():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s, execute_at=None)

    result = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    assert result.valid is True


# --- deterministic and idempotent --------------------------------------------------------------


def test_deterministic_repeated_validation():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, schedule = _scheduled(s)

    first = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)
    second = s["schedule_validation_service"].validate("task-1", schedule.schedule_id)

    assert first.valid == second.valid
    assert first.blocking_reasons == second.blocking_reasons
    assert first.preflight_id == second.preflight_id
