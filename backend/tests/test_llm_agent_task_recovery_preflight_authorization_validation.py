from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW
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
    AgentTaskRecoveryPreflightResult,
    InvalidAgentTaskRecoveryPreflightAuthorizationValidationError,
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightApprovalService,
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
    validation_service = LLMAgentTaskRecoveryPreflightAuthorizationValidationService(
        authorization_service=authorization_service, preflight_store=preflight_store,
        invalidation_service=invalidation_service, freshness_service=freshness_service,
        approval_service=approval_service, evaluation_service=evaluation_service,
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
        "validation_service": validation_service,
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


# --- valid path --------------------------------------------------------------


def test_valid_authorization_validates():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    result = s["validation_service"].validate("task-1", authorization.authorization_id)

    assert result.valid is True
    assert result.blocking_reasons == ()
    assert result.preflight_id == preflight.preflight_id
    assert result.task_id == "task-1"
    assert result.authorization_id == authorization.authorization_id
    assert isinstance(result.validated_at, datetime)
    assert s["validation_service"].is_valid("task-1", authorization.authorization_id) is True


def test_validate_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationValidationError):
        s["validation_service"].validate("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightAuthorizationValidationError):
        s["validation_service"].validate("task-1", "")


# --- missing --------------------------------------------------------------


def test_missing_authorization_is_invalid():
    s = _stack()

    result = s["validation_service"].validate("task-1", "never-existed")

    assert result.valid is False
    assert result.preflight_id is None
    assert any("no authorization is recorded" in r for r in result.blocking_reasons)
    assert s["validation_service"].is_valid("task-1", "never-existed") is False


def test_authorization_from_a_different_task_is_missing():
    s = _stack()
    _fail_task(s["event_service"])
    _, authorization = _authorized(s, task_id="task-1")

    result = s["validation_service"].validate("task-2", authorization.authorization_id)

    assert result.valid is False
    assert any("no authorization is recorded" in r for r in result.blocking_reasons)


# --- revoked --------------------------------------------------------------


def test_revoked_authorization_is_invalid():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)
    s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="operator revoked")

    result = s["validation_service"].validate("task-1", authorization.authorization_id)

    assert result.valid is False
    assert any("has been revoked" in r for r in result.blocking_reasons)
    assert result.preflight_id == preflight.preflight_id


# --- superseded --------------------------------------------------------------


def test_superseded_preflight_is_invalid():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

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

    result = s["validation_service"].validate("task-1", authorization.authorization_id)

    assert result.valid is False
    assert any("superseded" in r for r in result.blocking_reasons)


# --- invalidated --------------------------------------------------------------


def test_invalidated_preflight_is_invalid():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    result = s["validation_service"].validate("task-1", authorization.authorization_id)

    assert result.valid is False
    assert any("has been invalidated" in r for r in result.blocking_reasons)


# --- stale --------------------------------------------------------------


def test_stale_preflight_is_invalid():
    s = _stack()
    failure = _fail_task(s["event_service"])
    stale_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id="a-different-failure-id", failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY, reason="stale", priority=3, blocking_conditions=(),
    )
    preflight = s["preflight_store"].save(
        AgentTaskRecoveryPreflightResult(
            task_id="task-1", plan=stale_plan, guard_result=None, decision=ALLOW,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )
    # Bypass approval/authorization's own preflight-currency gates (they
    # would themselves refuse a stale plan) by directly assembling an
    # authorization pointing at it, so validate() is what is exercised.
    from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightApproval, PENDING, APPROVED

    approval = s["approval_service"]._store.save(
        AgentTaskRecoveryPreflightApproval(
            task_id="task-1", preflight_id=preflight.preflight_id, status=APPROVED,
            actor="alice", reason=None, created_at=datetime.now(timezone.utc), resolved_at=datetime.now(timezone.utc),
        )
    )
    from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightAuthorization, ACTIVE

    authorization = s["authorization_service"]._store.save(
        AgentTaskRecoveryPreflightAuthorization(
            task_id="task-1", preflight_id=preflight.preflight_id, approval_id=approval.approval_id,
            status=ACTIVE, revocation_reason=None, created_at=datetime.now(timezone.utc), revoked_at=None,
        )
    )

    result = s["validation_service"].validate("task-1", authorization.authorization_id)

    assert result.valid is False
    assert any(r.startswith("stale:") for r in result.blocking_reasons)


# --- policy-blocked --------------------------------------------------------------


def test_current_policy_denial_is_invalid():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    s["readiness"].set(policy_passed=False)

    result = s["validation_service"].validate("task-1", authorization.authorization_id)

    assert result.valid is False
    assert any("recovery guard/policy evaluation" in r for r in result.blocking_reasons)


# --- lapsed approval (not explicitly named but a listed check) --------------------------------------------------------------


def test_missing_preflight_is_invalid():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    # Simulate the referenced preflight no longer existing in history at all.
    empty_store = LLMAgentTaskRecoveryPreflightStore()
    isolated_validation_service = LLMAgentTaskRecoveryPreflightAuthorizationValidationService(
        authorization_service=s["authorization_service"], preflight_store=empty_store,
    )

    result = isolated_validation_service.validate("task-1", authorization.authorization_id)

    assert result.valid is False
    assert any("no longer exists" in r for r in result.blocking_reasons)


# --- regression: cannot silently remain usable after preflight becomes stale/invalid --------------------------------------------------------------


def test_authorization_cannot_remain_usable_after_becoming_invalidated():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)
    assert s["validation_service"].is_valid("task-1", authorization.authorization_id) is True

    s["invalidation_service"].invalidate("task-1", reason="a real problem was found")

    assert s["validation_service"].is_valid("task-1", authorization.authorization_id) is False
    # Commit #9's own cheap check agrees, but for a different (narrower) reason:
    assert s["authorization_service"].is_authorized("task-1", preflight.preflight_id) is True


def test_authorization_cannot_remain_usable_after_being_superseded():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)
    assert s["validation_service"].is_valid("task-1", authorization.authorization_id) is True

    s["readiness"].set(policy_passed=False)
    s["invalidation_service"].invalidate("task-1", reason="force rebuild")
    s["revalidation_service"].revalidate("task-1")

    assert s["validation_service"].is_valid("task-1", authorization.authorization_id) is False


# --- multiple simultaneous reasons --------------------------------------------------------------


def test_multiple_blocking_reasons_are_all_reported():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    s["authorization_service"].revoke("task-1", authorization.authorization_id, reason="revoked for testing")
    s["invalidation_service"].invalidate("task-1", reason="also invalidated")

    result = s["validation_service"].validate("task-1", authorization.authorization_id)

    assert result.valid is False
    assert len(result.blocking_reasons) >= 2


# --- deterministic --------------------------------------------------------------


def test_deterministic_repeated_validation():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    first = s["validation_service"].validate("task-1", authorization.authorization_id)
    second = s["validation_service"].validate("task-1", authorization.authorization_id)

    assert first.valid == second.valid
    assert first.blocking_reasons == second.blocking_reasons
    assert first.warnings == second.warnings
    assert first.preflight_id == second.preflight_id


# --- no recovery execution / no mutation --------------------------------------------------------------


def test_validation_does_not_mutate_task_state():
    s = _stack()
    _fail_task(s["event_service"])
    preflight, authorization = _authorized(s)

    before_classification = s["classifier"].classify("task-1")
    before_replay = s["replay_service"].replay("task-1")

    s["validation_service"].validate("task-1", authorization.authorization_id)

    after_classification = s["classifier"].classify("task-1")
    after_replay = s["replay_service"].replay("task-1")

    assert before_classification == after_classification
    assert before_replay == after_replay
    # The authorization/invalidation stores are also untouched by a pure validate() call.
    assert s["authorization_service"].get("task-1", authorization.authorization_id).status == "active"
