import pytest

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_policy_risk_assessment import LEVEL_HIGH, LEVEL_LOW
from backend.agent_policy_risk_thresholds import REVIEW
from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
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
    InvalidAgentTaskRecoveryGuardEvaluationError,
    InvalidAgentTaskRecoveryGuardError,
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
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
    def __init__(self, eligible=True, dead_letter_required=False, reason="eligible"):
        self._result = RetryEligibilityResult(
            task_id="unused", eligible=eligible, reason=reason, attempt_count=1, remaining_attempts=2,
            dead_letter_required=dead_letter_required,
        )

    def check(self, task_id):
        return self._result


class _FakeRetryScheduler:
    def __init__(self, schedule=None):
        self._schedule = schedule

    def get_retry_schedule(self, task_id):
        return self._schedule


class _FakeDeadLetterService:
    def __init__(self, entry=None):
        self._entry = entry

    def get(self, task_id):
        return self._entry


class _FakeReservationService:
    def __init__(self, valid=False):
        self._valid = valid

    def is_reservation_valid(self, task_id):
        return self._valid


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


def _fully_wired_guard(classifier, replay_service, **overrides):
    kwargs = dict(
        classifier=classifier,
        replay_service=replay_service,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=True),
        retry_scheduler=_FakeRetryScheduler(schedule=None),
        dead_letter_service=_FakeDeadLetterService(entry=None),
        reservation_service=_FakeReservationService(valid=False),
    )
    kwargs.update(overrides)
    return LLMAgentTaskRecoveryGuardService(**kwargs)


# --- clean plan -> allow --------------------------------------------------------------


def test_clean_plan_is_allowed():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure)
    guard = _fully_wired_guard(classifier, replay_service)
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)

    evaluation = evaluator.evaluate("task-1", plan)

    assert evaluation.decision == ALLOW
    assert evaluation.blocking_rules == ()
    assert evaluation.warnings == ()
    assert evaluation.risk_level is None
    assert "allowed" in evaluation.reason
    assert evaluation.recommended_action == RECOVERY_ACTION_RETRY


def test_evaluate_propagates_guard_argument_errors():
    _, classifier, replay_service = _stack()
    guard = _fully_wired_guard(classifier, replay_service)
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)

    with pytest.raises(InvalidAgentTaskRecoveryGuardError):
        evaluator.evaluate("", "not-a-plan")


# --- hard violation -> deny --------------------------------------------------------------


def test_hard_violation_is_denied():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    guard = _fully_wired_guard(
        classifier, replay_service, readiness_service=_FakeReadinessService(policy_passed=False)
    )
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)

    evaluation = evaluator.evaluate("task-1", plan)

    assert evaluation.decision == DENY
    assert len(evaluation.blocking_rules) == 1
    assert "not currently permitted" in evaluation.blocking_rules[0]
    assert "denied" in evaluation.reason


# --- review-required condition where supported --------------------------------------------------------------


def test_guard_warning_is_a_review_condition():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_WAIT_FOR_DEPENDENCY)
    guard = _fully_wired_guard(
        classifier, replay_service, readiness_service=_FakeReadinessService(dependencies_passed=False)
    )
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)

    evaluation = evaluator.evaluate("task-1", plan)

    assert evaluation.decision == REVIEW
    assert evaluation.blocking_rules == ()
    assert any("still unresolved" in w for w in evaluation.warnings)
    assert "requires review" in evaluation.reason


# --- multiple violations --------------------------------------------------------------


def test_multiple_violations_still_deny_with_all_reasons_present():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    guard = _fully_wired_guard(
        classifier,
        replay_service,
        readiness_service=_FakeReadinessService(policy_passed=False, dependencies_passed=False),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=False, reason="exhausted"),
    )
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)

    evaluation = evaluator.evaluate("task-1", plan)

    assert evaluation.decision == DENY
    assert len(evaluation.blocking_rules) >= 3
    assert evaluation.blocking_rules[0] in evaluation.reason or all(
        rule in evaluation.reason for rule in evaluation.blocking_rules
    )


# --- unknown condition --------------------------------------------------------------


def test_unverified_condition_is_review_not_allow():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_MARK_UNRECOVERABLE)
    # No readiness/retry/scheduler/dead-letter/reservation collaborators at
    # all -- the guard itself reports allowed=True with zero violations,
    # but almost nothing was actually verified.
    guard = LLMAgentTaskRecoveryGuardService(classifier=classifier, replay_service=replay_service)
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)

    evaluation = evaluator.evaluate("task-1", plan)

    assert evaluation.decision == REVIEW
    assert evaluation.blocking_rules == ()
    assert any("was never verified" in w for w in evaluation.warnings)
    assert any("action_permission" in w for w in evaluation.warnings)


def test_retry_budget_only_expected_for_retry_action():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_MARK_UNRECOVERABLE)
    guard = _fully_wired_guard(classifier, replay_service, retry_eligibility_service=None)
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)

    evaluation = evaluator.evaluate("task-1", plan)

    # retry_budget is inapplicable for this action, so its absence must
    # not itself trigger a review.
    assert not any("retry_budget" in w for w in evaluation.warnings)
    assert evaluation.decision == ALLOW


def test_retry_budget_missing_for_retry_action_triggers_review():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    guard = _fully_wired_guard(classifier, replay_service, retry_eligibility_service=None)
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)

    evaluation = evaluator.evaluate("task-1", plan)

    assert evaluation.decision == REVIEW
    assert any("retry_budget" in w for w in evaluation.warnings)


# --- existing policy/risk integration --------------------------------------------------------------


def test_risk_level_resolver_populates_risk_level():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure)
    guard = _fully_wired_guard(classifier, replay_service)
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(
        guard_service=guard, risk_level_resolver=lambda task_id, plan, guard_result: LEVEL_HIGH
    )

    evaluation = evaluator.evaluate("task-1", plan)

    assert evaluation.risk_level == LEVEL_HIGH


def test_risk_level_defaults_to_none_without_resolver():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure)
    guard = _fully_wired_guard(classifier, replay_service)
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)

    evaluation = evaluator.evaluate("task-1", plan)

    assert evaluation.risk_level is None


def test_risk_level_resolver_returning_invalid_value_raises():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure)
    guard = _fully_wired_guard(classifier, replay_service)
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(
        guard_service=guard, risk_level_resolver=lambda task_id, plan, guard_result: "SUPER_DUPER_RISKY"
    )

    with pytest.raises(InvalidAgentTaskRecoveryGuardEvaluationError):
        evaluator.evaluate("task-1", plan)


def test_risk_level_resolver_returning_none_is_accepted():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure)
    guard = _fully_wired_guard(classifier, replay_service)
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(
        guard_service=guard, risk_level_resolver=lambda task_id, plan, guard_result: None
    )

    evaluation = evaluator.evaluate("task-1", plan)

    assert evaluation.risk_level is None


# --- deterministic evaluation --------------------------------------------------------------


def test_deterministic_repeated_evaluation():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure)
    guard = _fully_wired_guard(classifier, replay_service)
    evaluator = LLMAgentTaskRecoveryGuardEvaluationService(
        guard_service=guard, risk_level_resolver=lambda task_id, plan, guard_result: LEVEL_LOW
    )

    first = evaluator.evaluate("task-1", plan)
    second = evaluator.evaluate("task-1", plan)

    assert first == second
