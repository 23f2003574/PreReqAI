from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_RETRY,
    RECOVERY_PRIORITY_HIGH,
    RECOVERY_PRIORITY_LOW,
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
from backend.agent_policy_engine import ALLOW
from backend.agent_task_recovery_guardrails import (
    AgentTaskRecoveryPreflightResult,
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightApprovalService,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightAuthorizationValidationService,
    LLMAgentTaskRecoveryPreflightFreshnessService,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightService,
    LLMAgentTaskRecoveryPreflightStore,
)
from backend.agent_task_recovery_scheduling import (
    InvalidAgentTaskRecoverySchedulePriorityError,
    LLMAgentTaskRecoveryPreflightSchedulePriorityService,
    LLMAgentTaskRecoveryPreflightSchedulingService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
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


def _stack(readiness=None):
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
    authorization_validation_service = LLMAgentTaskRecoveryPreflightAuthorizationValidationService(
        authorization_service=authorization_service, preflight_store=preflight_store,
        invalidation_service=invalidation_service, freshness_service=freshness_service,
        approval_service=approval_service, evaluation_service=evaluation_service,
    )
    scheduling_service = LLMAgentTaskRecoveryPreflightSchedulingService(
        approval_service=approval_service, authorization_service=authorization_service,
        validation_service=authorization_validation_service,
    )
    schedule_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
    )
    priority_service = LLMAgentTaskRecoveryPreflightSchedulePriorityService(
        scheduling_service=scheduling_service, validation_service=schedule_validation_service,
        preflight_store=preflight_store, evaluation_service=evaluation_service,
    )
    return {
        "event_service": event_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "scheduling_service": scheduling_service,
        "priority_service": priority_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _scheduled_via_run(s, task_id):
    """A schedule whose plan comes from the real planner (RETRY, HIGH priority)."""
    _fail_task(s["event_service"], task_id=task_id)
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    return s["scheduling_service"].schedule(task_id, preflight.preflight_id)


def _scheduled_with_plan(s, task_id, action, priority, execute_at=None):
    """A schedule built from a directly-constructed plan, for control
    over its own recovery_priority in tests."""
    failure = _fail_task(s["event_service"], task_id=task_id)
    plan = AgentTaskFailureRecoveryPlan(
        task_id=task_id, failure_event_id=failure.event_id, failure_category="execution",
        recommended_action=action, reason="test", priority=priority, blocking_conditions=(),
    )
    preflight = s["preflight_store"].save(
        AgentTaskRecoveryPreflightResult(
            task_id=task_id, plan=plan, guard_result=None, decision=ALLOW,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    return s["scheduling_service"].schedule(task_id, preflight.preflight_id, execute_at=execute_at)


# --- deterministic ordering / urgency differences --------------------------------------------------------------


def test_higher_recovery_priority_ranks_first():
    s = _stack()
    low = _scheduled_with_plan(s, "task-low", RECOVERY_ACTION_MARK_UNRECOVERABLE, RECOVERY_PRIORITY_LOW)
    high = _scheduled_with_plan(s, "task-high", RECOVERY_ACTION_RETRY, RECOVERY_PRIORITY_HIGH)

    ranked = s["priority_service"].prioritize("task-high", schedules=[low, high])

    assert [r.schedule_id for r in ranked] == [high.schedule_id, low.schedule_id]
    assert ranked[0].recovery_priority == RECOVERY_PRIORITY_HIGH


def test_priority_rejects_blank_task_id():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoverySchedulePriorityError):
        s["priority_service"].prioritize("")


def test_priority_unknown_schedule_raises():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoverySchedulePriorityError):
        s["priority_service"].priority("task-1", "never-existed")


# --- equal-priority ties --------------------------------------------------------------


def test_equal_priority_ties_broken_deterministically():
    s = _stack()
    a = _scheduled_with_plan(s, "task-a", RECOVERY_ACTION_RETRY, RECOVERY_PRIORITY_HIGH)
    b = _scheduled_with_plan(s, "task-b", RECOVERY_ACTION_RETRY, RECOVERY_PRIORITY_HIGH)

    first = s["priority_service"].prioritize("task-a", schedules=[a, b])
    second = s["priority_service"].prioritize("task-a", schedules=[a, b])

    assert [r.schedule_id for r in first] == [r.schedule_id for r in second]
    expected_order = sorted([a.schedule_id, b.schedule_id])
    assert [r.schedule_id for r in first] == expected_order


# --- earlier deadline ranks first (retry/deadline information) --------------------------------------------------------------


def test_earlier_execute_at_ranks_first_among_equal_priority():
    s = _stack()
    now = datetime.now(timezone.utc)
    # Both windows have already arrived (so both are actionable); the
    # more-overdue one should still rank first as the earlier deadline.
    later = _scheduled_with_plan(
        s, "task-later", RECOVERY_ACTION_RETRY, RECOVERY_PRIORITY_HIGH, execute_at=now - timedelta(hours=1)
    )
    sooner = _scheduled_with_plan(
        s, "task-sooner", RECOVERY_ACTION_RETRY, RECOVERY_PRIORITY_HIGH, execute_at=now - timedelta(hours=2)
    )

    ranked = s["priority_service"].prioritize("task-sooner", schedules=[later, sooner])

    assert [r.schedule_id for r in ranked] == [sooner.schedule_id, later.schedule_id]


# --- invalid schedules excluded --------------------------------------------------------------


def test_cancelled_schedule_is_excluded_from_ranking():
    s = _stack()
    schedule = _scheduled_via_run(s, "task-1")
    s["scheduling_service"].cancel("task-1", schedule.schedule_id)

    ranked = s["priority_service"].prioritize("task-1")
    assert ranked == ()

    factors = s["priority_service"].priority("task-1", schedule.schedule_id)
    assert factors.actionable is False
    assert factors.recovery_priority is None


def test_invalidated_schedule_is_excluded_from_ranking():
    s = _stack()
    schedule = _scheduled_via_run(s, "task-1")
    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    ranked = s["priority_service"].prioritize("task-1")
    assert ranked == ()


# --- policy/risk constraints --------------------------------------------------------------


def test_policy_blocked_schedule_never_becomes_actionable_via_priority():
    s = _stack()
    schedule = _scheduled_via_run(s, "task-1")
    s["readiness"].set(policy_passed=False)

    ranked = s["priority_service"].prioritize("task-1")
    assert ranked == ()
    assert s["priority_service"].priority("task-1", schedule.schedule_id).actionable is False


# --- existing queue-priority (recovery priority) integration --------------------------------------------------------------


def test_priority_factors_are_explainable():
    s = _stack()
    schedule = _scheduled_via_run(s, "task-1")

    factors = s["priority_service"].priority("task-1", schedule.schedule_id)

    assert factors.actionable is True
    assert factors.recovery_priority == RECOVERY_PRIORITY_HIGH
    assert any("recovery_priority" in f for f in factors.factors)


# --- never executes or authorizes recovery --------------------------------------------------------------


def test_prioritization_never_mutates_task_or_authorization_state():
    s = _stack()
    schedule = _scheduled_via_run(s, "task-1")
    before = s["authorization_service"].get("task-1", schedule.authorization_id)

    s["priority_service"].prioritize("task-1")
    s["priority_service"].priority("task-1", schedule.schedule_id)

    after = s["authorization_service"].get("task-1", schedule.authorization_id)
    assert before == after
    assert before.status == "active"
