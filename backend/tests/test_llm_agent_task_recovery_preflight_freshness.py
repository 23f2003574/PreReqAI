import pytest

from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
    RECOVERY_PRIORITY_HIGH,
    AgentTaskFailureRecoveryPlan,
    LLMAgentTaskEventFailureClassifier,
)
from backend.agent_task_events import (
    DEPENDENCY_REMOVED,
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
    AgentTaskRecoveryPreflight,
    InvalidAgentTaskRecoveryPreflightFreshnessError,
    LLMAgentTaskRecoveryPreflightFreshnessService,
    LLMAgentTaskRecoveryPreflightStore,
)


class _FakeReadinessService:
    def __init__(self, policy_passed=True, dependencies_passed=True, dependencies_detail=None):
        checks = [
            AgentTaskReadinessCheck(name="lifecycle_state", passed=True),
            AgentTaskReadinessCheck(
                name="dependencies",
                passed=dependencies_passed,
                detail=None if dependencies_passed else (dependencies_detail or "dependency X is not yet resolved"),
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


def _fail_dependency_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    event_service.emit(task_id, DEPENDENCY_REMOVED, payload={"dependency_id": "dep-1"})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _plan(task_id, failure, action=RECOVERY_ACTION_RETRY, category="execution"):
    return AgentTaskFailureRecoveryPlan(
        task_id=task_id, failure_event_id=failure.event_id if failure else None, failure_category=category,
        recommended_action=action, reason="test plan", priority=RECOVERY_PRIORITY_HIGH, blocking_conditions=(),
    )


def _preflight_record(task_id, plan, decision="ALLOW", store=None):
    store = store if store is not None else LLMAgentTaskRecoveryPreflightStore()
    from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult
    from datetime import datetime, timezone

    return store.save(
        AgentTaskRecoveryPreflightResult(
            task_id=task_id, plan=plan, guard_result=None, decision=decision,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )


def _freshness_service(classifier, replay_service, preflight_store, **kwargs):
    return LLMAgentTaskRecoveryPreflightFreshnessService(
        preflight_store=preflight_store, classifier=classifier, replay_service=replay_service, **kwargs
    )


# --- unchanged task -> fresh --------------------------------------------------------------


def test_unchanged_task_is_fresh():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure)
    preflight = _preflight_record("task-1", plan, store=store)
    service = _freshness_service(
        classifier, replay_service, store,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=True),
    )

    result = service.check("task-1")

    assert result.is_fresh is True
    assert result.stale_reasons == ()
    assert "task_state" in result.checked_references
    assert "plan_identity" in result.checked_references


def test_check_rejects_blank_task_id():
    _, classifier, replay_service = _stack()
    store = LLMAgentTaskRecoveryPreflightStore()
    service = _freshness_service(classifier, replay_service, store)
    with pytest.raises(InvalidAgentTaskRecoveryPreflightFreshnessError):
        service.check("")


def test_check_rejects_task_id_mismatch_for_supplied_preflight():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-2", failure)
    preflight = _preflight_record("task-2", plan, store=store)
    service = _freshness_service(classifier, replay_service, store)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightFreshnessError):
        service.check("task-1", preflight=preflight)


# --- changed task state -> stale --------------------------------------------------------------


def test_changed_task_state_is_stale():
    event_service, classifier, replay_service = _stack()
    # The task is only READY (not yet failed) at preflight time -- FAILED
    # is terminal (no outgoing TRANSITIONS edges), so to legally observe a
    # REAL state change afterward the preflight must be checked before the
    # task actually reaches FAILED.
    event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": "ready"})
    store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure=None, action=RECOVERY_ACTION_MARK_UNRECOVERABLE)
    preflight = _preflight_record("task-1", plan, store=store)

    # Now the task actually fails, after the preflight was already checked.
    event_service.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    service = _freshness_service(
        classifier, replay_service, store,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=True),
    )

    result = service.check("task-1")

    assert result.is_fresh is False
    assert any("task state changed" in reason for reason in result.stale_reasons)


# --- changed failure/plan reference -> stale --------------------------------------------------------------


def test_changed_failure_reference_is_stale():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    store = LLMAgentTaskRecoveryPreflightStore()
    stale_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id="a-different-failure-id", failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY, reason="stale", priority=RECOVERY_PRIORITY_HIGH,
        blocking_conditions=(),
    )
    preflight = _preflight_record("task-1", stale_plan, store=store)
    service = _freshness_service(
        classifier, replay_service, store,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=True),
    )

    result = service.check("task-1")

    assert result.is_fresh is False
    assert any("no longer matches the task's current failure" in reason for reason in result.stale_reasons)


def test_changed_failure_category_is_stale():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure, category="dependency")
    preflight = _preflight_record("task-1", plan, store=store)
    service = _freshness_service(
        classifier, replay_service, store,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=True),
    )

    result = service.check("task-1")

    assert result.is_fresh is False
    assert any("failure_category has changed" in reason for reason in result.stale_reasons)


# --- changed relevant dependency/retry condition --------------------------------------------------------------


def test_resolved_dependency_condition_makes_wait_plan_stale():
    event_service, classifier, replay_service = _stack()
    failure = _fail_dependency_task(event_service)
    store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_WAIT_FOR_DEPENDENCY, category="dependency")
    preflight = _preflight_record("task-1", plan, store=store)
    # dependency now resolved, unlike when the plan was made
    service = _freshness_service(
        classifier, replay_service, store, readiness_service=_FakeReadinessService(dependencies_passed=True)
    )

    result = service.check("task-1")

    assert result.is_fresh is False
    assert any("dependency condition" in reason and "resolved" in reason for reason in result.stale_reasons)


def test_lost_retry_eligibility_makes_retry_plan_stale():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    preflight = _preflight_record("task-1", plan, store=store)
    service = _freshness_service(
        classifier, replay_service, store,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=False, reason="max attempts exceeded"),
    )

    result = service.check("task-1")

    assert result.is_fresh is False
    assert any("retry eligibility has changed" in reason for reason in result.stale_reasons)


def test_policy_now_denying_is_stale_regardless_of_action():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_MARK_UNRECOVERABLE)
    preflight = _preflight_record("task-1", plan, store=store)
    service = _freshness_service(
        classifier, replay_service, store, readiness_service=_FakeReadinessService(policy_passed=False)
    )

    result = service.check("task-1")

    assert result.is_fresh is False
    assert any("no longer permitted" in reason for reason in result.stale_reasons)


# --- missing comparison evidence --------------------------------------------------------------


def test_missing_readiness_and_retry_collaborators_is_not_silently_fresh():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    preflight = _preflight_record("task-1", plan, store=store)
    service = _freshness_service(classifier, replay_service, store)  # no readiness/retry collaborators at all

    result = service.check("task-1")

    assert result.is_fresh is False
    assert any("action permission could not be verified" in reason for reason in result.stale_reasons)
    assert any("retry eligibility could not be verified" in reason for reason in result.stale_reasons)


def test_no_stored_preflight_is_not_silently_fresh():
    _, classifier, replay_service = _stack()
    store = LLMAgentTaskRecoveryPreflightStore()
    service = _freshness_service(classifier, replay_service, store)

    result = service.check("never-preflighted-task")

    assert result.is_fresh is False
    assert any("no stored preflight" in reason for reason in result.stale_reasons)
    assert result.checked_references == ()


# --- old preflight with otherwise stable state --------------------------------------------------------------


def test_old_preflight_with_stable_state_is_still_fresh():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure)

    from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult
    from datetime import datetime, timedelta, timezone

    # "Old" here means a long time has elapsed since checked_at, not that
    # checked_at predates the task's own real events (which would instead
    # exercise the task_state check, not this one) -- a checked_at set
    # well into the future of those events is the honest way to represent
    # "much later" without excluding any of them from the point-in-time
    # replay boundary.
    old_checked_at = datetime.now(timezone.utc) + timedelta(days=30)
    preflight = store.save(
        AgentTaskRecoveryPreflightResult(
            task_id="task-1", plan=plan, guard_result=None, decision="ALLOW",
            blocking_reasons=(), warnings=(), checked_at=old_checked_at,
        )
    )
    service = _freshness_service(
        classifier, replay_service, store,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=True),
    )

    result = service.check("task-1")

    assert result.is_fresh is True
    assert result.stale_reasons == ()


# --- deterministic repeated checks --------------------------------------------------------------


def test_deterministic_repeated_checks():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    store = LLMAgentTaskRecoveryPreflightStore()
    plan = _plan("task-1", failure)
    _preflight_record("task-1", plan, store=store)
    service = _freshness_service(
        classifier, replay_service, store,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=True),
    )

    first = service.check("task-1")
    second = service.check("task-1")

    assert first == second
