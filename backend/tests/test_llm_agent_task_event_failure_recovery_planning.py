from types import SimpleNamespace

import pytest

from backend.agent_task_context import UnknownTaskContextError
from backend.agent_task_event_analytics import (
    FAILURE_CATEGORY_CONTEXT,
    FAILURE_CATEGORY_DEPENDENCY,
    FAILURE_CATEGORY_EXECUTION,
    FAILURE_CATEGORY_TIMEOUT_CANCELLATION,
    FAILURE_CATEGORY_VALIDATION_POLICY,
    InvalidAgentTaskFailureRecoveryPlanError,
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskEventFailureRecoveryPlanner,
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_NONE,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_UNRESOLVED,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
)
from backend.agent_task_events import (
    CONTEXT_UPDATED,
    DEPENDENCY_REMOVED,
    InMemoryAgentTaskEventStore,
    LIFECYCLE_TRANSITIONED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventService,
    READINESS_CHANGED,
)
from backend.agent_task_lifecycle import CANCELLED, FAILED, PLANNED


def _services():
    store = InMemoryAgentTaskEventStore()
    emitter = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    return emitter, classifier


def _planner(classifier, **collaborators):
    return LLMAgentTaskEventFailureRecoveryPlanner(classifier=classifier, **collaborators)


class _FakeReadinessCheck:
    def __init__(self, name, passed, detail=None):
        self.name = name
        self.passed = passed
        self.detail = detail


class _FakeReadinessResult:
    def __init__(self, checks, blocking_reasons=()):
        self.checks = checks
        self.blocking_reasons = list(blocking_reasons)


class _FakeReadinessService:
    def __init__(self, result):
        self._result = result

    def check(self, task_id):
        return self._result


class _FakeEligibilityResult:
    def __init__(self, eligible, reason, dead_letter_required=False):
        self.eligible = eligible
        self.reason = reason
        self.dead_letter_required = dead_letter_required


class _FakeRetryEligibilityService:
    def __init__(self, result):
        self._result = result

    def check(self, task_id):
        return self._result


class _FakeContextService:
    def __init__(self, exists):
        self._exists = exists

    def get(self, task_id):
        if not self._exists:
            raise UnknownTaskContextError(task_id)
        return SimpleNamespace(task_id=task_id)


# --- retryable failure -----------------------------------------------------------------------


def test_retryable_failure_recommends_retry():
    emitter, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    failing = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    eligibility_service = _FakeRetryEligibilityService(_FakeEligibilityResult(eligible=True, reason="ok"))
    planner = _planner(classifier, retry_eligibility_service=eligibility_service)

    plan = planner.plan("task-1")

    assert plan.failure_event_id == failing.event_id
    assert plan.failure_category == FAILURE_CATEGORY_EXECUTION
    assert plan.recommended_action == RECOVERY_ACTION_RETRY
    assert plan.blocking_conditions == ()


def test_plan_rejects_blank_task_id():
    _, classifier = _services()
    planner = _planner(classifier)

    with pytest.raises(InvalidAgentTaskFailureRecoveryPlanError):
        planner.plan("")


def test_retryable_failure_without_eligibility_service_is_unresolved():
    emitter, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    planner = _planner(classifier)  # no eligibility/repair service supplied

    plan = planner.plan("task-1")

    assert plan.recommended_action == RECOVERY_ACTION_UNRESOLVED


# --- dependency failure -------------------------------------------------------------------------


def test_dependency_failure_still_blocked_recommends_wait():
    emitter, classifier = _services()
    emitter.emit("task-1", DEPENDENCY_REMOVED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    readiness_result = _FakeReadinessResult(
        checks=[_FakeReadinessCheck("dependencies", passed=False, detail="dependency 'task-0' has not completed yet")]
    )
    planner = _planner(classifier, readiness_service=_FakeReadinessService(readiness_result))

    plan = planner.plan("task-1")

    assert plan.failure_category == FAILURE_CATEGORY_DEPENDENCY
    assert plan.recommended_action == RECOVERY_ACTION_WAIT_FOR_DEPENDENCY
    assert plan.blocking_conditions == ("dependency 'task-0' has not completed yet",)


def test_dependency_failure_without_readiness_service_is_unresolved():
    emitter, classifier = _services()
    emitter.emit("task-1", DEPENDENCY_REMOVED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    planner = _planner(classifier)

    plan = planner.plan("task-1")

    assert plan.recommended_action == RECOVERY_ACTION_UNRESOLVED


# --- context failure -----------------------------------------------------------------------------


def test_context_failure_with_existing_record_recommends_refresh():
    emitter, classifier = _services()
    emitter.emit("task-1", CONTEXT_UPDATED)
    failing = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    planner = _planner(classifier, context_service=_FakeContextService(exists=True))

    plan = planner.plan("task-1")

    assert plan.failure_category == FAILURE_CATEGORY_CONTEXT
    assert plan.recommended_action == RECOVERY_ACTION_REFRESH_CONTEXT
    assert plan.failure_event_id == failing.event_id


def test_context_failure_with_no_record_is_unresolved():
    emitter, classifier = _services()
    emitter.emit("task-1", CONTEXT_UPDATED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    planner = _planner(classifier, context_service=_FakeContextService(exists=False))

    plan = planner.plan("task-1")

    assert plan.recommended_action == RECOVERY_ACTION_UNRESOLVED


# --- terminal/unrecoverable failure -----------------------------------------------------------------


def test_cancelled_task_recommends_mark_unrecoverable():
    emitter, classifier = _services()
    cancelled = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": CANCELLED})

    planner = _planner(classifier)

    plan = planner.plan("task-1")

    assert plan.failure_category == FAILURE_CATEGORY_TIMEOUT_CANCELLATION
    assert plan.recommended_action == RECOVERY_ACTION_MARK_UNRECOVERABLE
    assert plan.failure_event_id == cancelled.event_id


def test_exhausted_retries_with_dead_letter_required_recommends_mark_unrecoverable():
    emitter, classifier = _services()
    emitter.emit("task-1", "retry_scheduled")
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    eligibility_service = _FakeRetryEligibilityService(
        _FakeEligibilityResult(eligible=False, reason="max attempts reached", dead_letter_required=True)
    )
    planner = _planner(classifier, retry_eligibility_service=eligibility_service)

    plan = planner.plan("task-1")

    assert plan.recommended_action == RECOVERY_ACTION_MARK_UNRECOVERABLE


def test_validation_policy_failure_recommends_mark_unrecoverable():
    emitter, classifier = _services()
    emitter.emit("task-1", READINESS_CHANGED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    planner = _planner(classifier)

    plan = planner.plan("task-1")

    assert plan.failure_category == FAILURE_CATEGORY_VALIDATION_POLICY
    assert plan.recommended_action == RECOVERY_ACTION_MARK_UNRECOVERABLE


# --- multiple failures ----------------------------------------------------------------------------------


def test_multiple_failures_resolve_to_the_terminal_one():
    emitter, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    first = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})  # reaffirmation, noise

    planner = _planner(classifier)

    plan = planner.plan("task-1")

    assert plan.failure_event_id == first.event_id  # the one replay() actually validated


# --- conflicting recovery signals -------------------------------------------------------------------------


def test_dependency_no_longer_blocking_overrides_stale_wait_recommendation():
    emitter, classifier = _services()
    emitter.emit("task-1", DEPENDENCY_REMOVED)
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    # historically classified as "dependency," but the live readiness check
    # now reports dependencies are satisfied -- waiting further would be stale
    readiness_result = _FakeReadinessResult(checks=[_FakeReadinessCheck("dependencies", passed=True)])
    planner = _planner(classifier, readiness_service=_FakeReadinessService(readiness_result))

    plan = planner.plan("task-1")

    assert plan.failure_category == FAILURE_CATEGORY_DEPENDENCY  # classification itself is untouched
    assert plan.recommended_action == RECOVERY_ACTION_RETRY  # but the action reflects live state
    assert plan.blocking_conditions == ()


# --- unknown failure --------------------------------------------------------------------------------------


def test_unknown_failure_is_explicitly_unresolved():
    emitter, classifier = _services()
    failing = emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})  # no preceding event

    planner = _planner(classifier)

    plan = planner.plan("task-1")

    assert plan.failure_event_id == failing.event_id
    assert plan.recommended_action == RECOVERY_ACTION_UNRESOLVED


# --- no failures -------------------------------------------------------------------------------------------


def test_no_failures_produces_no_action_plan():
    emitter, classifier = _services()
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})

    planner = _planner(classifier)

    plan = planner.plan("task-1")

    assert plan.failure_event_id is None
    assert plan.failure_category is None
    assert plan.recommended_action == RECOVERY_ACTION_NONE
    assert plan.blocking_conditions == ()


def test_empty_stream_produces_no_action_plan():
    _, classifier = _services()
    planner = _planner(classifier)

    plan = planner.plan("task-1")

    assert plan.recommended_action == RECOVERY_ACTION_NONE


# --- deterministic output -----------------------------------------------------------------------------------


def test_repeated_planning_is_deterministic():
    emitter, classifier = _services()
    emitter.emit("task-1", "retry_scheduled")
    emitter.emit("task-1", LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})

    eligibility_service = _FakeRetryEligibilityService(_FakeEligibilityResult(eligible=True, reason="ok"))
    planner = _planner(classifier, retry_eligibility_service=eligibility_service)

    first = planner.plan("task-1")
    second = planner.plan("task-1")

    assert first == second
