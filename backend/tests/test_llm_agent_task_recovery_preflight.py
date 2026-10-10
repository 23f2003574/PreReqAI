from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_policy_risk_thresholds import REVIEW
from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
    RECOVERY_PRIORITY_HIGH,
    AgentTaskFailureRecoveryPlan,
    InvalidAgentTaskFailureRecoveryPlanError,
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskEventFailureRecoveryPlanner,
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
    InvalidAgentTaskRecoveryGuardError,
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightService,
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


class _BrokenReadinessService:
    def check(self, task_id):
        raise RuntimeError("readiness backend is unreachable")


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


class _FakeRetryScheduler:
    def get_retry_schedule(self, task_id):
        return None


class _FakeDeadLetterService:
    def get(self, task_id):
        return None


class _FakeReservationService:
    def is_reservation_valid(self, task_id):
        return False


def _fully_wired_guard(classifier, replay_service, **overrides):
    kwargs = dict(
        classifier=classifier,
        replay_service=replay_service,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=True),
        retry_scheduler=_FakeRetryScheduler(),
        dead_letter_service=_FakeDeadLetterService(),
        reservation_service=_FakeReservationService(),
    )
    kwargs.update(overrides)
    return LLMAgentTaskRecoveryGuardService(**kwargs)


def _preflight_service(classifier, replay_service, planner=None, guard=None):
    guard = guard if guard is not None else _fully_wired_guard(classifier, replay_service)
    evaluation_service = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)
    planner = (
        planner
        if planner is not None
        else LLMAgentTaskEventFailureRecoveryPlanner(
            classifier=classifier, retry_eligibility_service=_FakeRetryEligibilityService(eligible=True)
        )
    )
    return LLMAgentTaskRecoveryPreflightService(planner=planner, evaluation_service=evaluation_service)


# --- valid recovery -> executable --------------------------------------------------------------


def test_valid_recovery_is_executable():
    event_service, classifier, replay_service = _stack()
    _fail_task(event_service)
    preflight = _preflight_service(classifier, replay_service)

    result = preflight.run("task-1")

    assert result.decision == ALLOW
    assert result.plan is not None
    assert result.plan.recommended_action == RECOVERY_ACTION_RETRY
    assert result.guard_result is not None
    assert result.blocking_reasons == ()
    assert result.task_id == "task-1"
    assert isinstance(result.checked_at, datetime)


# --- blocked recovery --------------------------------------------------------------


def test_blocked_recovery_is_denied():
    event_service, classifier, replay_service = _stack()
    _fail_task(event_service)
    guard = _fully_wired_guard(classifier, replay_service, readiness_service=_FakeReadinessService(policy_passed=False))
    preflight = _preflight_service(classifier, replay_service, guard=guard)

    result = preflight.run("task-1")

    assert result.decision == DENY
    assert len(result.blocking_reasons) >= 1
    assert result.plan is not None


# --- planner failure --------------------------------------------------------------


def test_planner_failure_reports_instead_of_fabricating_a_plan():
    event_service, classifier, replay_service = _stack()
    _fail_dependency_task(event_service)
    broken_planner = LLMAgentTaskEventFailureRecoveryPlanner(
        classifier=classifier, readiness_service=_BrokenReadinessService()
    )
    preflight = _preflight_service(classifier, replay_service, planner=broken_planner)

    result = preflight.run("task-1")

    assert result.plan is None
    assert result.guard_result is None
    assert result.decision == DENY
    assert any("recovery planning failed" in reason for reason in result.blocking_reasons)


def test_planner_argument_error_still_propagates():
    _, classifier, replay_service = _stack()
    preflight = _preflight_service(classifier, replay_service)

    with pytest.raises(InvalidAgentTaskFailureRecoveryPlanError):
        preflight.run("")


# --- changed task state --------------------------------------------------------------


def test_stale_externally_supplied_plan_is_denied():
    event_service, classifier, replay_service = _stack()
    _fail_task(event_service)
    preflight = _preflight_service(classifier, replay_service)
    stale_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id="stale-failure-id", failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY, reason="stale", priority=RECOVERY_PRIORITY_HIGH,
        blocking_conditions=(),
    )

    result = preflight.run_plan("task-1", stale_plan)

    assert result.decision == DENY
    assert any("plan is stale" in reason for reason in result.blocking_reasons)


def test_run_plan_propagates_guard_argument_errors():
    _, classifier, replay_service = _stack()
    preflight = _preflight_service(classifier, replay_service)
    plan = AgentTaskFailureRecoveryPlan(
        task_id="task-2", failure_event_id=None, failure_category=None,
        recommended_action=RECOVERY_ACTION_RETRY, reason="x", priority=RECOVERY_PRIORITY_HIGH, blocking_conditions=(),
    )

    with pytest.raises(InvalidAgentTaskRecoveryGuardError):
        preflight.run_plan("task-1", plan)


# --- warnings without blockers --------------------------------------------------------------


def test_warnings_without_blockers_is_review():
    event_service, classifier, replay_service = _stack()
    _fail_dependency_task(event_service)
    guard = _fully_wired_guard(classifier, replay_service, readiness_service=_FakeReadinessService(dependencies_passed=False))
    planner = LLMAgentTaskEventFailureRecoveryPlanner(
        classifier=classifier, readiness_service=_FakeReadinessService(dependencies_passed=False)
    )
    preflight = _preflight_service(classifier, replay_service, planner=planner, guard=guard)

    result = preflight.run("task-1")

    assert result.plan.recommended_action == RECOVERY_ACTION_WAIT_FOR_DEPENDENCY
    assert result.decision == REVIEW
    assert result.blocking_reasons == ()
    assert any("still unresolved" in w for w in result.warnings)


# --- repeated preflight --------------------------------------------------------------


def test_repeated_preflight_is_deterministic():
    event_service, classifier, replay_service = _stack()
    _fail_task(event_service)
    preflight = _preflight_service(classifier, replay_service)
    fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    first = preflight.run("task-1", now=fixed_now)
    second = preflight.run("task-1", now=fixed_now)

    assert first == second
    assert first.checked_at == fixed_now


def test_checked_at_defaults_to_current_time_when_not_supplied():
    event_service, classifier, replay_service = _stack()
    _fail_task(event_service)
    preflight = _preflight_service(classifier, replay_service)

    before = datetime.now(timezone.utc)
    result = preflight.run("task-1")
    after = datetime.now(timezone.utc)

    assert before <= result.checked_at <= after


# --- verify no task mutation --------------------------------------------------------------


def test_preflight_never_mutates_task_state():
    event_service, classifier, replay_service = _stack()
    _fail_task(event_service)
    preflight = _preflight_service(classifier, replay_service)

    before_classification = classifier.classify("task-1")
    before_replay = replay_service.replay("task-1")

    preflight.run("task-1")
    preflight.run("task-1")

    after_classification = classifier.classify("task-1")
    after_replay = replay_service.replay("task-1")

    assert before_classification == after_classification
    assert before_replay == after_replay
