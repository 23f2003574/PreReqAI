from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_RETRY,
    AgentTaskFailureRecoveryPlan,
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
    ACTIVE,
    REVOKED,
    AgentTaskRecoveryPreflightResult,
    InvalidAgentTaskRecoveryPreflightAuthorizationError,
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightApprovalService,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
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


def _stack(readiness=None, retry_eligibility=None):
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
    return {
        "event_service": event_service,
        "classifier": classifier,
        "replay_service": replay_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "revalidation_service": revalidation_service,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _approved_preflight(s, task_id="task-1"):
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    return preflight


# --- approved current preflight authorizes --------------------------------------------------------------


def test_approved_current_preflight_authorizes():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)

    authorization = s["authorization_service"].authorize("task-1", preflight.preflight_id)

    assert authorization.status == ACTIVE
    assert authorization.task_id == "task-1"
    assert authorization.preflight_id == preflight.preflight_id
    assert authorization.revoked_at is None
    assert s["authorization_service"].is_authorized("task-1", preflight.preflight_id) is True


def test_authorize_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].authorize("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].authorize("task-1", "")


# --- pending/rejected preflight denied --------------------------------------------------------------


def test_pending_preflight_cannot_be_authorized():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)  # never approved

    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].authorize("task-1", preflight.preflight_id)


def test_rejected_preflight_cannot_be_authorized():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)
    s["approval_service"].reject("task-1", preflight.preflight_id, actor="bob", reason="no")

    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].authorize("task-1", preflight.preflight_id)


def test_never_requested_preflight_cannot_be_authorized():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))

    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].authorize("task-1", preflight.preflight_id)


# --- stale/invalidated/superseded preflight denied --------------------------------------------------------------


def test_invalidated_preflight_cannot_be_authorized():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].authorize("task-1", preflight.preflight_id)


def test_superseded_preflight_cannot_be_authorized():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)

    newer_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id="a-different-failure-id", failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY, reason="newer", priority=3, blocking_conditions=(),
    )
    s["preflight_store"].save(
        AgentTaskRecoveryPreflightResult(
            task_id="task-1", plan=newer_plan, guard_result=None, decision=ALLOW,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].authorize("task-1", preflight.preflight_id)


# --- guard/policy failure denies authorization --------------------------------------------------------------


def test_current_guard_policy_failure_denies_authorization():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)

    # Conditions change after approval, before authorization is attempted.
    s["readiness"].set(policy_passed=False)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].authorize("task-1", preflight.preflight_id)


# --- authorization is bound to exact preflight --------------------------------------------------------------


def test_authorization_is_bound_to_exact_preflight():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    authorization = s["authorization_service"].authorize("task-1", preflight.preflight_id)

    assert s["authorization_service"].get("task-1", authorization.authorization_id) == authorization
    assert s["authorization_service"].get("task-2", authorization.authorization_id) is None
    assert s["authorization_service"].is_authorized("task-1", "some-other-preflight-id") is False


# --- revoked authorization cannot be reused --------------------------------------------------------------


def test_revoked_authorization_cannot_be_reused():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    authorization = s["authorization_service"].authorize("task-1", preflight.preflight_id)

    revoked = s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="operator revoked")

    assert revoked.status == REVOKED
    assert revoked.revocation_reason == "operator revoked"
    assert s["authorization_service"].is_authorized("task-1", preflight.preflight_id) is False

    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].authorize("task-1", preflight.preflight_id)


def test_repeated_revoke_is_idempotent():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    authorization = s["authorization_service"].authorize("task-1", preflight.preflight_id)

    first = s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="first reason")
    second = s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="second reason")

    assert first == second
    assert second.revocation_reason == "first reason"


def test_revoke_unknown_authorization_raises():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].revoke("task-1", "never-existed", reason="x")


def test_revoke_requires_reason():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    authorization = s["authorization_service"].authorize("task-1", preflight.preflight_id)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationError):
        s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="")


# --- revalidation invalidates previous authorization --------------------------------------------------------------


def test_revalidation_invalidates_previous_authorization():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)
    authorization = s["authorization_service"].authorize("task-1", preflight.preflight_id)
    assert s["authorization_service"].is_authorized("task-1", preflight.preflight_id) is True

    s["readiness"].set(policy_passed=False)
    s["invalidation_service"].invalidate("task-1", reason="force rebuild")
    revalidation = s["revalidation_service"].revalidate("task-1")
    assert revalidation.current_preflight_id != preflight.preflight_id

    # The OLD authorization's own stored record is untouched (history
    # preserved) but it no longer counts as currently usable.
    stored = s["authorization_service"].get("task-1", authorization.authorization_id)
    assert stored.status == ACTIVE
    assert s["authorization_service"].is_authorized("task-1", preflight.preflight_id) is False


# --- repeated authorization is idempotent --------------------------------------------------------------


def test_repeated_authorization_is_idempotent():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)

    first = s["authorization_service"].authorize("task-1", preflight.preflight_id)
    second = s["authorization_service"].authorize("task-1", preflight.preflight_id)

    assert first == second


# --- authorization persistence/history works --------------------------------------------------------------


def test_authorization_persistence_across_two_preflights():
    s = _stack()
    _fail_task(s["event_service"])
    first_preflight = _approved_preflight(s)
    first_authorization = s["authorization_service"].authorize("task-1", first_preflight.preflight_id)
    s["authorization_service"].revoke("task-1", first_authorization.authorization_id, reason="superseded manually")

    second_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id=first_preflight.plan.failure_event_id,
        failure_category=first_preflight.plan.failure_category,
        recommended_action=RECOVERY_ACTION_RETRY, reason="re-evaluated", priority=3, blocking_conditions=(),
    )
    second_preflight = s["preflight_store"].save(
        AgentTaskRecoveryPreflightResult(
            task_id="task-1", plan=second_plan, guard_result=None, decision=ALLOW,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )
    s["approval_service"].request("task-1", second_preflight.preflight_id)
    s["approval_service"].approve("task-1", second_preflight.preflight_id, actor="alice")
    second_authorization = s["authorization_service"].authorize("task-1", second_preflight.preflight_id)

    assert s["authorization_service"].get("task-1", first_authorization.authorization_id).status == REVOKED
    assert s["authorization_service"].get("task-1", second_authorization.authorization_id).status == ACTIVE


# --- recovery itself is never executed --------------------------------------------------------------


def test_no_task_state_mutation_occurs():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = _approved_preflight(s)

    before_classification = s["classifier"].classify("task-1")
    before_replay = s["replay_service"].replay("task-1")

    s["authorization_service"].authorize("task-1", preflight.preflight_id)

    after_classification = s["classifier"].classify("task-1")
    after_replay = s["replay_service"].replay("task-1")

    assert before_classification == after_classification
    assert before_replay == after_replay
