from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_RETRY,
    RECOVERY_PRIORITY_HIGH,
    AgentTaskFailureRecoveryPlan,
    LLMAgentTaskEventFailureClassifier,
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
    InvalidAgentTaskRecoveryPreflightInvalidationError,
    LLMAgentTaskRecoveryPreflightFreshnessService,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightStore,
)


class _FakeReadinessService:
    def __init__(self, policy_passed=True, dependencies_passed=True):
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


def _stack():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    replay_service = LLMAgentTaskEventReplayService(query_service=query_service)
    return event_service, classifier, replay_service


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _plan(task_id, failure, action=RECOVERY_ACTION_RETRY, category="execution"):
    return AgentTaskFailureRecoveryPlan(
        task_id=task_id, failure_event_id=failure.event_id, failure_category=category,
        recommended_action=action, reason="test plan", priority=RECOVERY_PRIORITY_HIGH, blocking_conditions=(),
    )


def _save_preflight(preflight_store, task_id, plan, decision=ALLOW):
    return preflight_store.save(
        AgentTaskRecoveryPreflightResult(
            task_id=task_id, plan=plan, guard_result=None, decision=decision,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )


def _invalidation_service(preflight_store, classifier, replay_service, **freshness_kwargs):
    freshness_service = LLMAgentTaskRecoveryPreflightFreshnessService(
        preflight_store=preflight_store, classifier=classifier, replay_service=replay_service, **freshness_kwargs
    )
    return LLMAgentTaskRecoveryPreflightInvalidationService(
        preflight_store=preflight_store, freshness_service=freshness_service
    )


# --- stale preflight gets invalidated --------------------------------------------------------------


def test_stale_preflight_gets_invalidated():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    stale_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id="a-different-failure-id", failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY, reason="stale", priority=RECOVERY_PRIORITY_HIGH,
        blocking_conditions=(),
    )
    saved = _save_preflight(preflight_store, "task-1", stale_plan)
    service = _invalidation_service(
        preflight_store, classifier, replay_service,
        readiness_service=_FakeReadinessService(), retry_eligibility_service=_FakeRetryEligibilityService(),
    )

    result = service.invalidate_if_stale("task-1")

    assert result.is_invalid is True
    assert result.preflight_id == saved.preflight_id
    assert "stale" in result.reason
    assert result.previous_decision == ALLOW


# --- fresh preflight remains valid --------------------------------------------------------------


def test_fresh_preflight_remains_valid():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure)
    saved = _save_preflight(preflight_store, "task-1", plan)
    service = _invalidation_service(
        preflight_store, classifier, replay_service,
        readiness_service=_FakeReadinessService(), retry_eligibility_service=_FakeRetryEligibilityService(),
    )

    result = service.invalidate_if_stale("task-1")

    assert result.is_invalid is False
    assert result.preflight_id == saved.preflight_id
    assert result.invalidated_at is None
    assert result.reason is None


# --- explicit invalidation --------------------------------------------------------------


def test_explicit_invalidation():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure)
    saved = _save_preflight(preflight_store, "task-1", plan, decision=DENY)
    service = _invalidation_service(preflight_store, classifier, replay_service)

    result = service.invalidate("task-1", reason="manually revoked by an operator")

    assert result.is_invalid is True
    assert result.reason == "manually revoked by an operator"
    assert result.previous_decision == DENY
    assert result.preflight_id == saved.preflight_id


def test_explicit_invalidation_default_reason():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure)
    _save_preflight(preflight_store, "task-1", plan)
    service = _invalidation_service(preflight_store, classifier, replay_service)

    result = service.invalidate("task-1")

    assert result.is_invalid is True
    assert result.reason == "explicitly invalidated"


def test_invalidate_rejects_blank_task_id():
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    service = LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=preflight_store)
    with pytest.raises(InvalidAgentTaskRecoveryPreflightInvalidationError):
        service.invalidate("")


# --- repeated invalidation is idempotent --------------------------------------------------------------


def test_repeated_explicit_invalidation_is_idempotent():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure)
    _save_preflight(preflight_store, "task-1", plan)
    service = _invalidation_service(preflight_store, classifier, replay_service)

    first = service.invalidate("task-1", reason="first reason")
    second = service.invalidate("task-1", reason="a completely different reason")

    assert first == second
    assert second.reason == "first reason"


def test_repeated_invalidate_if_stale_is_idempotent():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    stale_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id="a-different-failure-id", failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY, reason="stale", priority=RECOVERY_PRIORITY_HIGH,
        blocking_conditions=(),
    )
    _save_preflight(preflight_store, "task-1", stale_plan)
    service = _invalidation_service(
        preflight_store, classifier, replay_service,
        readiness_service=_FakeReadinessService(), retry_eligibility_service=_FakeRetryEligibilityService(),
    )

    first = service.invalidate_if_stale("task-1")
    second = service.invalidate_if_stale("task-1")

    assert first == second


def test_explicitly_invalidated_preflight_is_not_revived_by_invalidate_if_stale():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure)  # a plan that is otherwise still perfectly fresh
    saved = _save_preflight(preflight_store, "task-1", plan)
    service = _invalidation_service(
        preflight_store, classifier, replay_service,
        readiness_service=_FakeReadinessService(), retry_eligibility_service=_FakeRetryEligibilityService(),
    )

    explicit = service.invalidate("task-1", reason="operator judgment, unrelated to task state")
    assert explicit.is_invalid is True

    # Nothing about the task changed -- a bare freshness check would say
    # fresh -- but the explicit invalidation must still stand.
    result = service.invalidate_if_stale("task-1")

    assert result.is_invalid is True
    assert result.reason == "operator judgment, unrelated to task state"
    assert result.preflight_id == saved.preflight_id


# --- reason preservation --------------------------------------------------------------


def test_reason_is_preserved_verbatim():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure)
    _save_preflight(preflight_store, "task-1", plan)
    service = _invalidation_service(preflight_store, classifier, replay_service)

    result = service.invalidate("task-1", reason="operator suspected a bad plan")

    assert result.reason == "operator suspected a bad plan"


# --- history retains the original record --------------------------------------------------------------


def test_history_retains_the_original_preflight_record():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure)
    saved = _save_preflight(preflight_store, "task-1", plan)
    service = _invalidation_service(preflight_store, classifier, replay_service)

    service.invalidate("task-1", reason="operator call")

    history = preflight_store.history("task-1")
    assert len(history) == 1
    assert history[0] == saved
    assert history[0].decision == ALLOW  # never rewritten to reflect invalidation


# --- missing preflight handled cleanly --------------------------------------------------------------


def test_missing_preflight_handled_cleanly_for_invalidate():
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    service = LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=preflight_store)

    result = service.invalidate("never-preflighted-task")

    assert result.preflight_id is None
    assert result.is_invalid is False
    assert result.invalidated_at is None
    assert result.reason is None


def test_missing_preflight_handled_cleanly_for_invalidate_if_stale():
    _, classifier, replay_service = _stack()
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    service = _invalidation_service(preflight_store, classifier, replay_service)

    result = service.invalidate_if_stale("never-preflighted-task")

    assert result.preflight_id is None
    assert result.is_invalid is False
