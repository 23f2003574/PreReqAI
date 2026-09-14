import pytest

from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_RETRY,
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
    CONSUMED,
    CONSUMPTION_FAILED,
    DENIED,
    InvalidAgentTaskRecoveryConsumptionAuditError,
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightApprovalService,
    LLMAgentTaskRecoveryPreflightAuthorizationConsumptionService,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightAuthorizationValidationService,
    LLMAgentTaskRecoveryPreflightConsumptionAuditService,
    LLMAgentTaskRecoveryPreflightFreshnessService,
    LLMAgentTaskRecoveryPreflightInvalidationService,
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
    audit_service = LLMAgentTaskRecoveryPreflightConsumptionAuditService(authorization_service=authorization_service)
    consumption_service = LLMAgentTaskRecoveryPreflightAuthorizationConsumptionService(
        validation_service=validation_service, preflight_store=preflight_store, execution_service=execution_service,
        audit_service=audit_service,
    )
    audit_service._consumption_service = consumption_service
    return {
        "event_service": event_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "consumption_service": consumption_service,
        "audit_service": audit_service,
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


# --- successful consumption audit --------------------------------------------------------------


def test_successful_consumption_is_audited():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    consumption = s["consumption_service"].consume("task-1", authorization.authorization_id)
    entry = s["audit_service"].get("task-1", authorization.authorization_id)

    assert entry.outcome == CONSUMED
    assert entry.task_id == "task-1"
    assert entry.authorization_id == authorization.authorization_id
    assert entry.preflight_id == preflight.preflight_id
    assert entry.execution_reference == consumption.consumption_id


def test_record_attempt_rejects_bad_outcome():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryConsumptionAuditError):
        s["audit_service"].record_attempt("task-1", "auth-1", "not-a-real-outcome")


# --- denied consumption audit --------------------------------------------------------------


def test_denied_consumption_is_audited():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)  # never approved

    from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightAuthorization, ACTIVE
    from datetime import datetime, timezone

    fake_authorization = s["authorization_service"]._store.save(
        AgentTaskRecoveryPreflightAuthorization(
            task_id="task-1", preflight_id=preflight.preflight_id, approval_id="never-approved",
            status=ACTIVE, revocation_reason=None, created_at=datetime.now(timezone.utc), revoked_at=None,
        )
    )

    with pytest.raises(Exception):
        s["consumption_service"].consume("task-1", fake_authorization.authorization_id)

    entry = s["audit_service"].get("task-1", fake_authorization.authorization_id)
    assert entry.outcome == DENIED
    assert entry.reason is not None


# --- stale/revoked authorization audit --------------------------------------------------------------


def test_revoked_authorization_denial_is_audited():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)
    s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="operator revoked")

    with pytest.raises(Exception):
        s["consumption_service"].consume("task-1", authorization.authorization_id)

    entry = s["audit_service"].get("task-1", authorization.authorization_id)
    assert entry.outcome == DENIED
    assert "revoked" in entry.reason


def test_invalidated_preflight_denial_is_audited():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    with pytest.raises(Exception):
        s["consumption_service"].consume("task-1", authorization.authorization_id)

    entry = s["audit_service"].get("task-1", authorization.authorization_id)
    assert entry.outcome == DENIED


# --- duplicate-consumption audit --------------------------------------------------------------


def test_duplicate_consumption_is_audited_separately():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    s["consumption_service"].consume("task-1", authorization.authorization_id)
    s["consumption_service"].consume("task-1", authorization.authorization_id)

    entries = [e for e in s["audit_service"].list("task-1") if e.authorization_id == authorization.authorization_id]
    assert len(entries) == 2
    assert entries[0].outcome == CONSUMED
    assert entries[1].outcome == CONSUMED
    assert "duplicate" in entries[1].reason


# --- failed recovery execution audit --------------------------------------------------------------


def test_failed_execution_is_audited():
    s = _stack(wire_execution=False)
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    consumption = s["consumption_service"].consume("task-1", authorization.authorization_id)
    entry = s["audit_service"].get("task-1", authorization.authorization_id)

    assert consumption.outcome == "failed"
    assert entry.outcome == CONSUMPTION_FAILED
    assert entry.execution_reference == consumption.consumption_id


# --- correct task/authorization/preflight linkage --------------------------------------------------------------


def test_audit_entries_isolated_across_tasks():
    s = _stack()
    _fail_task(s["event_service"], task_id="task-1")
    _, authorization_1 = _authorized(s, task_id="task-1")
    s["consumption_service"].consume("task-1", authorization_1.authorization_id)

    assert s["audit_service"].get("task-2", authorization_1.authorization_id) is None
    entries = s["audit_service"].list("task-1")
    assert all(e.task_id == "task-1" for e in entries)


# --- history remains append-only --------------------------------------------------------------


def test_audit_history_is_append_only():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    s["consumption_service"].consume("task-1", authorization.authorization_id)
    s["consumption_service"].consume("task-1", authorization.authorization_id)
    s["consumption_service"].consume("task-1", authorization.authorization_id)

    entries = s["audit_service"].list("task-1")
    assert len(entries) == 3
    # Original entries never rewritten:
    assert entries[0].outcome == CONSUMED
    assert entries[0].reason is None


# --- audit failure cannot cause duplicate recovery execution --------------------------------------------------------------


class _BrokenAuditService:
    def record_attempt(self, *args, **kwargs):
        raise RuntimeError("audit backend is down")


def test_audit_failure_does_not_prevent_or_duplicate_execution():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)
    s["consumption_service"]._audit_service = _BrokenAuditService()

    consumption = s["consumption_service"].consume("task-1", authorization.authorization_id)
    second = s["consumption_service"].consume("task-1", authorization.authorization_id)

    assert consumption == second
    assert consumption.outcome == "success"
