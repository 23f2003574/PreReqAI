import pytest

from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
    RECOVERY_PRIORITY_HIGH,
    RECOVERY_PRIORITY_LOW,
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
from backend.agent_task_lifecycle import CANCELLED, FAILED, PLANNED, READY
from backend.agent_task_queue_dead_letter import DeadLetterEntry
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult
from backend.agent_task_queue_retry_scheduler import CANCELLED as SCHEDULE_CANCELLED
from backend.agent_task_queue_retry_scheduler import SCHEDULED, TaskRetrySchedule
from backend.agent_task_readiness import AgentTaskReadinessCheck, AgentTaskReadinessResult
from backend.agent_task_recovery_guardrails import (
    InvalidAgentTaskRecoveryGuardError,
    LLMAgentTaskRecoveryGuardService,
)
from datetime import datetime, timedelta, timezone


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


def _plan(task_id, failure, action=RECOVERY_ACTION_RETRY, category="execution", priority=RECOVERY_PRIORITY_HIGH):
    return AgentTaskFailureRecoveryPlan(
        task_id=task_id,
        failure_event_id=failure.event_id,
        failure_category=category,
        recommended_action=action,
        reason="test plan",
        priority=priority,
        blocking_conditions=(),
    )


# --- valid recovery --------------------------------------------------------------


def test_valid_recovery_is_allowed():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure)
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier,
        replay_service=replay_service,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=True),
        retry_scheduler=_FakeRetryScheduler(schedule=None),
        reservation_service=_FakeReservationService(valid=False),
    )

    result = guard.validate("task-1", plan)

    assert result.allowed is True
    assert result.violations == ()
    assert result.recommended_action == RECOVERY_ACTION_RETRY
    assert "task_eligibility" in result.checked_conditions
    assert "plan_freshness" in result.checked_conditions
    assert "action_permission" in result.checked_conditions
    assert "retry_budget" in result.checked_conditions
    assert "dependency_readiness" in result.checked_conditions
    assert "conflicting_recovery" in result.checked_conditions
    assert "active_reservation" in result.checked_conditions


def test_validate_rejects_blank_task_id():
    _, classifier, replay_service = _stack()
    guard = LLMAgentTaskRecoveryGuardService(classifier=classifier, replay_service=replay_service)
    plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id=None, failure_category=None,
        recommended_action=RECOVERY_ACTION_RETRY, reason="x", priority=RECOVERY_PRIORITY_LOW, blocking_conditions=(),
    )
    with pytest.raises(InvalidAgentTaskRecoveryGuardError):
        guard.validate("", plan)


def test_validate_rejects_wrong_type():
    _, classifier, replay_service = _stack()
    guard = LLMAgentTaskRecoveryGuardService(classifier=classifier, replay_service=replay_service)
    with pytest.raises(InvalidAgentTaskRecoveryGuardError):
        guard.validate("task-1", "not-a-plan")


def test_validate_rejects_task_id_mismatch():
    _, classifier, replay_service = _stack()
    guard = LLMAgentTaskRecoveryGuardService(classifier=classifier, replay_service=replay_service)
    plan = AgentTaskFailureRecoveryPlan(
        task_id="task-2", failure_event_id=None, failure_category=None,
        recommended_action=RECOVERY_ACTION_RETRY, reason="x", priority=RECOVERY_PRIORITY_LOW, blocking_conditions=(),
    )
    with pytest.raises(InvalidAgentTaskRecoveryGuardError):
        guard.validate("task-1", plan)


# --- exhausted retry/budget limit --------------------------------------------------------------


def test_exhausted_retry_budget_is_a_violation():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier,
        replay_service=replay_service,
        retry_eligibility_service=_FakeRetryEligibilityService(
            eligible=False, dead_letter_required=True, reason="max attempts exceeded"
        ),
    )

    result = guard.validate("task-1", plan)

    assert result.allowed is False
    assert any("not currently eligible" in v for v in result.violations)


def test_retry_budget_not_checked_for_non_retry_action():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_MARK_UNRECOVERABLE)
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier,
        replay_service=replay_service,
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=False),
    )

    result = guard.validate("task-1", plan)

    assert "retry_budget" not in result.checked_conditions
    assert result.allowed is True


# --- blocked dependency --------------------------------------------------------------


def test_blocked_dependency_is_a_violation_for_retry():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier,
        replay_service=replay_service,
        readiness_service=_FakeReadinessService(dependencies_passed=False),
    )

    result = guard.validate("task-1", plan)

    assert result.allowed is False
    assert any("resolved dependencies" in v for v in result.violations)


def test_blocked_dependency_is_only_a_warning_for_wait_action():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_WAIT_FOR_DEPENDENCY)
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier,
        replay_service=replay_service,
        readiness_service=_FakeReadinessService(dependencies_passed=False),
    )

    result = guard.validate("task-1", plan)

    assert result.allowed is True
    assert result.violations == ()
    assert any("still unresolved" in w for w in result.warnings)


# --- changed task state --------------------------------------------------------------


def test_stale_plan_against_changed_failure_is_a_violation():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    stale_plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    # The plan's own failure_event_id is now bogus / no longer the task's real one.
    stale_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id="stale-failure-id", failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY, reason="stale", priority=RECOVERY_PRIORITY_HIGH,
        blocking_conditions=(),
    )

    guard = LLMAgentTaskRecoveryGuardService(classifier=classifier, replay_service=replay_service)
    result = guard.validate("task-1", stale_plan)

    assert result.allowed is False
    assert any("plan is stale" in v for v in result.violations)


def test_stale_plan_against_changed_category_is_a_violation():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY, category="dependency")

    guard = LLMAgentTaskRecoveryGuardService(classifier=classifier, replay_service=replay_service)
    result = guard.validate("task-1", plan)

    assert result.allowed is False
    assert any("failure_category has changed" in v for v in result.violations)


# --- disallowed action --------------------------------------------------------------


def test_disallowed_action_is_a_violation():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier,
        replay_service=replay_service,
        readiness_service=_FakeReadinessService(policy_passed=False),
    )

    result = guard.validate("task-1", plan)

    assert result.allowed is False
    assert any("not currently permitted" in v for v in result.violations)


# --- active conflicting recovery --------------------------------------------------------------


def test_active_scheduled_retry_is_a_conflicting_violation():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    schedule = TaskRetrySchedule(
        task_id="task-1", attempt=2, scheduled_at=datetime.now(timezone.utc),
        eligible_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        status=SCHEDULED, reason="scheduled after prior failure",
    )
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier, replay_service=replay_service, retry_scheduler=_FakeRetryScheduler(schedule=schedule)
    )

    result = guard.validate("task-1", plan)

    assert result.allowed is False
    assert any("already scheduled" in v for v in result.violations)


def test_cancelled_schedule_is_not_a_conflict():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    schedule = TaskRetrySchedule(
        task_id="task-1", attempt=2, scheduled_at=datetime.now(timezone.utc),
        eligible_at=datetime.now(timezone.utc), status=SCHEDULE_CANCELLED, reason="x",
    )
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier, replay_service=replay_service, retry_scheduler=_FakeRetryScheduler(schedule=schedule)
    )

    result = guard.validate("task-1", plan)

    assert result.allowed is True


def test_active_reservation_is_a_conflicting_violation():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier, replay_service=replay_service, reservation_service=_FakeReservationService(valid=True)
    )

    result = guard.validate("task-1", plan)

    assert result.allowed is False
    assert any("active reservation" in v for v in result.violations)


# --- multiple violations --------------------------------------------------------------


def test_multiple_violations_are_all_reported():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    schedule = TaskRetrySchedule(
        task_id="task-1", attempt=2, scheduled_at=datetime.now(timezone.utc),
        eligible_at=datetime.now(timezone.utc), status=SCHEDULED, reason="x",
    )
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier,
        replay_service=replay_service,
        readiness_service=_FakeReadinessService(policy_passed=False, dependencies_passed=False),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=False, reason="exhausted"),
        retry_scheduler=_FakeRetryScheduler(schedule=schedule),
    )

    result = guard.validate("task-1", plan)

    assert result.allowed is False
    assert len(result.violations) >= 4


def test_task_already_completed_is_not_eligible_for_recovery():
    event_service, classifier, replay_service = _stack()
    task_id = "task-1"
    from backend.agent_task_lifecycle import COMPLETED, RUNNING

    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": READY})
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": RUNNING})
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": COMPLETED})
    plan = AgentTaskFailureRecoveryPlan(
        task_id=task_id, failure_event_id=None, failure_category=None,
        recommended_action=RECOVERY_ACTION_RETRY, reason="x", priority=RECOVERY_PRIORITY_LOW, blocking_conditions=(),
    )

    guard = LLMAgentTaskRecoveryGuardService(classifier=classifier, replay_service=replay_service)
    result = guard.validate(task_id, plan)

    assert result.allowed is False
    assert any("already completed" in v for v in result.violations)


def test_task_already_dead_lettered_is_a_violation():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier,
        replay_service=replay_service,
        dead_letter_service=_FakeDeadLetterService(entry=DeadLetterEntry(task_id="task-1", reason="prior")),
    )

    result = guard.validate("task-1", plan)

    assert result.allowed is False
    assert any("already been dead-lettered" in v for v in result.violations)


# --- unchanged valid plan --------------------------------------------------------------


def test_unchanged_valid_plan_repeated_validation_is_deterministic():
    event_service, classifier, replay_service = _stack()
    failure = _fail_task(event_service)
    plan = _plan("task-1", failure, action=RECOVERY_ACTION_RETRY)
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier,
        replay_service=replay_service,
        readiness_service=_FakeReadinessService(),
        retry_eligibility_service=_FakeRetryEligibilityService(eligible=True),
    )

    first = guard.validate("task-1", plan)
    second = guard.validate("task-1", plan)

    assert first == second
    assert first.allowed is True
