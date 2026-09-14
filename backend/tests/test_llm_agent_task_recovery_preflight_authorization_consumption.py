from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_RETRY,
    RECOVERY_OUTCOME_FAILED,
    RECOVERY_OUTCOME_SUCCESS,
    AgentTaskFailureRecoveryPlan,
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskEventFailureRecoveryPlanner,
    LLMAgentTaskFailureRecoveryService,
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
    AgentTaskRecoveryPreflightResult,
    InvalidAgentTaskRecoveryPreflightConsumptionError,
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightApprovalService,
    LLMAgentTaskRecoveryPreflightAuthorizationConsumptionService,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightAuthorizationValidationService,
    LLMAgentTaskRecoveryPreflightFreshnessService,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightRevalidationService,
    LLMAgentTaskRecoveryPreflightService,
    LLMAgentTaskRecoveryPreflightStore,
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


class _FakeExecutionRetryScheduler:
    """A fake for LLMAgentTaskFailureRecoveryService's own retry_scheduler
    collaborator -- distinct from the guard's own _FakeRetryScheduler."""

    class _Schedule:
        attempt = 1
        status = "SCHEDULED"

    def schedule_retry(self, task_id):
        return self._Schedule()


def _stack(readiness=None, retry_eligibility=None, wire_execution=True):
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    replay_service = LLMAgentTaskEventReplayService(query_service=query_service)

    readiness = readiness if readiness is not None else _FakeReadinessService()
    retry_eligibility = retry_eligibility if retry_eligibility is not None else _FakeRetryEligibilityService()

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
    revalidation_service = LLMAgentTaskRecoveryPreflightRevalidationService(
        preflight_store=preflight_store, preflight_service=preflight_service, invalidation_service=invalidation_service
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
    execution_service = LLMAgentTaskFailureRecoveryService(
        retry_scheduler=_FakeExecutionRetryScheduler() if wire_execution else None
    )
    consumption_service = LLMAgentTaskRecoveryPreflightAuthorizationConsumptionService(
        validation_service=validation_service, preflight_store=preflight_store, execution_service=execution_service,
    )
    return {
        "event_service": event_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "revalidation_service": revalidation_service,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "consumption_service": consumption_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _authorized(s, task_id="task-1"):
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    authorization = s["authorization_service"].authorize(task_id, preflight.preflight_id)
    return preflight, authorization


# --- valid authorization reaches existing recovery executor --------------------------------------------------------------


def test_valid_authorization_reaches_executor():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)
    assert preflight.plan.recommended_action == RECOVERY_ACTION_RETRY

    consumption = s["consumption_service"].consume("task-1", authorization.authorization_id)

    assert consumption.outcome == RECOVERY_OUTCOME_SUCCESS
    assert consumption.execution_result.success is True
    assert consumption.preflight_id == preflight.preflight_id
    assert consumption.authorization_id == authorization.authorization_id


def test_consume_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightConsumptionError):
        s["consumption_service"].consume("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightConsumptionError):
        s["consumption_service"].consume("task-1", "")


# --- invalid/revoked/stale authorization never executes --------------------------------------------------------------


def test_never_authorized_id_never_executes():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightConsumptionError):
        s["consumption_service"].consume("task-1", "never-existed")
    assert s["consumption_service"].get("task-1", "never-existed") is None


def test_revoked_authorization_never_executes():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)
    s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="operator revoked")

    with pytest.raises(InvalidAgentTaskRecoveryPreflightConsumptionError):
        s["consumption_service"].consume("task-1", authorization.authorization_id)
    assert s["consumption_service"].get("task-1", authorization.authorization_id) is None


def test_stale_invalidated_authorization_never_executes():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    with pytest.raises(InvalidAgentTaskRecoveryPreflightConsumptionError):
        s["consumption_service"].consume("task-1", authorization.authorization_id)


# --- wrong task/preflight binding is rejected --------------------------------------------------------------


def test_wrong_task_binding_is_rejected():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s, task_id="task-1")

    with pytest.raises(InvalidAgentTaskRecoveryPreflightConsumptionError):
        s["consumption_service"].consume("task-2", authorization.authorization_id)
    assert s["consumption_service"].get("task-2", authorization.authorization_id) is None


# --- already-consumed authorization cannot execute twice --------------------------------------------------------------


def test_already_consumed_authorization_returns_same_result_and_does_not_re_execute():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    first = s["consumption_service"].consume("task-1", authorization.authorization_id)
    # Revoking afterward proves a second consume() call does not re-validate/re-execute.
    s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="too late now")
    second = s["consumption_service"].consume("task-1", authorization.authorization_id)

    assert first == second
    assert first.consumption_id == second.consumption_id


# --- successful execution records consumption --------------------------------------------------------------


def test_successful_execution_records_consumption():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    consumption = s["consumption_service"].consume("task-1", authorization.authorization_id)

    stored = s["consumption_service"].get("task-1", authorization.authorization_id)
    assert stored == consumption
    assert stored.outcome == RECOVERY_OUTCOME_SUCCESS
    assert isinstance(stored.consumed_at, datetime)


# --- failed execution records failure --------------------------------------------------------------


def test_failed_execution_records_failure_without_retry():
    s = _stack(wire_execution=False)  # no retry_scheduler wired into the execution service
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    consumption = s["consumption_service"].consume("task-1", authorization.authorization_id)

    assert consumption.outcome == RECOVERY_OUTCOME_FAILED
    assert consumption.execution_result.success is False
    # And it is still recorded, not silently retried:
    assert s["consumption_service"].get("task-1", authorization.authorization_id) == consumption


# --- execution result/reference is preserved --------------------------------------------------------------


def test_execution_result_is_preserved_verbatim():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    consumption = s["consumption_service"].consume("task-1", authorization.authorization_id)

    assert consumption.execution_result.task_id == "task-1"
    assert consumption.execution_result.planned_action == RECOVERY_ACTION_RETRY
    assert consumption.execution_result.executed_action == RECOVERY_ACTION_RETRY


# --- existing recovery safeguards remain active --------------------------------------------------------------


def test_execution_still_goes_through_real_retry_scheduler_mechanism():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    consumption = s["consumption_service"].consume("task-1", authorization.authorization_id)

    assert "retry scheduled: attempt 1" in consumption.execution_result.affected_reference


# --- no duplicate execution on repeated calls --------------------------------------------------------------


def test_repeated_consume_calls_do_not_duplicate_records():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    s["consumption_service"].consume("task-1", authorization.authorization_id)
    s["consumption_service"].consume("task-1", authorization.authorization_id)
    s["consumption_service"].consume("task-1", authorization.authorization_id)

    # Preflight/approval/authorization history is untouched by repeated consumption.
    assert len(s["preflight_store"].history("task-1")) == 1
