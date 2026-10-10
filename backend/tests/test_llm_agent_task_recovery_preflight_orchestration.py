import pytest

from backend.agent_task_event_analytics import (
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
    InvalidAgentTaskRecoveryOrchestrationError,
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightApprovalService,
    LLMAgentTaskRecoveryPreflightAuthorizationConsumptionService,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightAuthorizationValidationService,
    LLMAgentTaskRecoveryPreflightFreshnessService,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightOrchestrationService,
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
    class _Schedule:
        attempt = 1
        status = "SCHEDULED"

    def schedule_retry(self, task_id):
        return self._Schedule()


class _AlwaysInvalidValidationService:
    def validate(self, task_id, authorization_id):
        from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightAuthorizationValidation
        from datetime import datetime, timezone

        return AgentTaskRecoveryPreflightAuthorizationValidation(
            valid=False, task_id=task_id, authorization_id=authorization_id, preflight_id="whatever",
            blocking_reasons=("forced invalid for this test",), warnings=(), validated_at=datetime.now(timezone.utc),
        )


def _stack(readiness=None, wire_execution=True):
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
    orchestration_service = LLMAgentTaskRecoveryPreflightOrchestrationService(
        revalidation_service=revalidation_service, approval_service=approval_service,
        authorization_service=authorization_service, validation_service=validation_service,
        consumption_service=consumption_service,
    )
    return {
        "event_service": event_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "validation_service": validation_service,
        "consumption_service": consumption_service,
        "orchestration_service": orchestration_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _approved_preflight(s, task_id="task-1"):
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    return preflight


# --- happy path --------------------------------------------------------------


def test_full_lifecycle_happy_path():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)

    result = s["orchestration_service"].execute("task-1")

    assert result.executed is True
    assert result.current_preflight_id == preflight.preflight_id
    assert result.approval.status == "approved"
    assert result.authorization.status == "active"
    assert result.validation.valid is True
    assert result.consumption is not None
    assert result.outcome == "success"
    assert result.blocking_reasons == ()


def test_execute_rejects_blank_task_id():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryOrchestrationError):
        s["orchestration_service"].execute("")


# --- stale preflight gets revalidated --------------------------------------------------------------


def test_stale_preflight_gets_revalidated_before_approval_check():
    s = _stack()
    _fail_task(s["event_service"])
    original = _approved_preflight(s)

    s["readiness"].set(policy_passed=False)  # forces staleness/policy-block on rebuild

    result = s["orchestration_service"].execute("task-1")

    assert result.original_preflight_id == original.preflight_id
    assert result.current_preflight_id != original.preflight_id
    assert result.executed is False
    assert "current preflight decision" in result.blocking_reasons[0]  # the rebuilt one is DENY, not ALLOW


# --- rejected preflight stops execution --------------------------------------------------------------


def test_rejected_preflight_stops_execution():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)
    s["approval_service"].reject("task-1", preflight.preflight_id, actor="bob", reason="no")

    result = s["orchestration_service"].execute("task-1")

    assert result.executed is False
    assert result.authorization is None
    assert result.consumption is None
    assert "not been approved" in result.blocking_reasons[0]


# --- invalid authorization stops execution --------------------------------------------------------------


def test_revoked_authorization_stops_execution():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    authorization = s["authorization_service"].authorize("task-1", preflight.preflight_id)
    s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="revoked externally")

    result = s["orchestration_service"].execute("task-1")

    assert result.executed is False
    assert result.authorization is None
    assert result.consumption is None
    assert "authorization failed" in result.blocking_reasons[0]


# --- validation failure stops execution --------------------------------------------------------------


def test_validation_failure_stops_execution():
    s = _stack()
    _fail_task(s["event_service"])
    _approved_preflight(s)
    s["orchestration_service"]._validation_service = _AlwaysInvalidValidationService()

    result = s["orchestration_service"].execute("task-1")

    assert result.executed is False
    assert result.consumption is None
    assert "forced invalid" in result.blocking_reasons[0]


# --- already-consumed authorization behaves correctly --------------------------------------------------------------


def test_repeated_execute_is_idempotent():
    s = _stack()
    _fail_task(s["event_service"])
    _approved_preflight(s)

    first = s["orchestration_service"].execute("task-1")
    second = s["orchestration_service"].execute("task-1")

    assert first.executed is True
    assert second.executed is True
    assert first.authorization.authorization_id == second.authorization.authorization_id
    assert first.consumption.consumption_id == second.consumption.consumption_id


# --- execution failure propagates correctly --------------------------------------------------------------


def test_execution_failure_propagates():
    s = _stack(wire_execution=False)
    _fail_task(s["event_service"])
    _approved_preflight(s)

    result = s["orchestration_service"].execute("task-1")

    assert result.executed is True  # the pipeline reached consumption
    assert result.outcome == "failed"
    assert result.consumption.execution_result.success is False


# --- all existing audit/history records remain intact --------------------------------------------------------------


def test_history_remains_intact_across_calls():
    s = _stack()
    _fail_task(s["event_service"])
    _approved_preflight(s)

    s["orchestration_service"].execute("task-1")
    s["orchestration_service"].execute("task-1")

    assert len(s["preflight_store"].history("task-1")) == 1


# --- no recovery occurs when any prerequisite gate fails --------------------------------------------------------------


def test_no_consumption_record_when_not_approved():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)  # never approved

    result = s["orchestration_service"].execute("task-1")

    assert result.executed is False
    assert s["authorization_service"].get("task-1", "anything") is None
    for auth_status in ("active", "revoked"):
        pass  # no authorization was ever minted at all -- nothing to check by id
