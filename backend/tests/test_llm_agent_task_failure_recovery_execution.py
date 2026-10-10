from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from backend.agent_task_event_analytics import (
    FAILURE_CATEGORY_EXECUTION,
    InvalidAgentTaskFailureRecoveryExecutionError,
    LLMAgentTaskFailureRecoveryService,
    RECOVERY_ACTION_MARK_UNRECOVERABLE,
    RECOVERY_ACTION_NONE,
    RECOVERY_ACTION_REFRESH_CONTEXT,
    RECOVERY_ACTION_REPAIR_TASK,
    RECOVERY_ACTION_RETRY,
    RECOVERY_ACTION_UNRESOLVED,
    RECOVERY_ACTION_WAIT_FOR_DEPENDENCY,
    RECOVERY_PRIORITY_HIGH,
    AgentTaskFailureRecoveryPlan,
)
from backend.agent_task_queue_retry_repair.models import CREATE, RepairOperation, RetryRepairPlan
from backend.agent_task_queue_retry_scheduler import IneligibleForRetryError, LLMAgentTaskRetryScheduler


def _plan(action, task_id="task-1", reason="because", **overrides):
    fields = dict(
        task_id=task_id,
        failure_event_id="event-1",
        failure_category=FAILURE_CATEGORY_EXECUTION,
        recommended_action=action,
        reason=reason,
        priority=RECOVERY_PRIORITY_HIGH,
        blocking_conditions=(),
    )
    fields.update(overrides)
    return AgentTaskFailureRecoveryPlan(**fields)


class _FakeRetryScheduler:
    def __init__(self, attempt=1, status="SCHEDULED", error=None):
        self._attempt = attempt
        self._status = status
        self._error = error
        self.calls = 0

    def schedule_retry(self, task_id):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return SimpleNamespace(task_id=task_id, attempt=self._attempt, status=self._status)

    def cancel_retry(self, task_id):
        pass

    @contextmanager
    def atomic(self):
        yield


class _FakeReadinessResult:
    def __init__(self, ready):
        self.ready = ready


class _FakeReadinessService:
    def __init__(self, ready):
        self._ready = ready

    def check(self, task_id):
        return _FakeReadinessResult(self._ready)


class _FakeQueueService:
    def __init__(self, priority=5, error=None):
        self._priority = priority
        self._error = error
        self.calls = 0

    def enqueue(self, task_id):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return SimpleNamespace(task_id=task_id, priority=self._priority)


class _FakeContextRefreshService:
    def __init__(self, added=None, removed=None, error=None):
        self._added = added or []
        self._removed = removed or []
        self._error = error

    def refresh(self, task_id):
        if self._error is not None:
            raise self._error
        return SimpleNamespace(task_id=task_id, added_sources=self._added, removed_sources=self._removed)


class _FakeRetryRepairService:
    def __init__(self, plan):
        self._plan = plan

    def plan_repair(self, task_id):
        return self._plan


class _FakeDeadLetterService:
    def __init__(self, error=None):
        self._error = error

    def dead_letter(self, task_id, reason):
        if self._error is not None:
            raise self._error
        return SimpleNamespace(task_id=task_id, reason=reason)


class _FakeEligibilityService:
    def check(self, task_id, now=None):
        return SimpleNamespace(eligible=True, attempt_count=0, next_eligible_at=None, reason="ok")


# --- successful retry --------------------------------------------------------------------------


def test_successful_retry_execution():
    service = LLMAgentTaskFailureRecoveryService(retry_scheduler=_FakeRetryScheduler(attempt=1))

    result = service.execute_plan(_plan(RECOVERY_ACTION_RETRY))

    assert result.success is True
    assert result.executed_action == RECOVERY_ACTION_RETRY
    assert result.planned_action == RECOVERY_ACTION_RETRY
    assert "attempt 1" in result.affected_reference


def test_execute_rejects_blank_task_id():
    service = LLMAgentTaskFailureRecoveryService()

    with pytest.raises(InvalidAgentTaskFailureRecoveryExecutionError):
        service.execute("")


def test_execute_plan_rejects_non_plan_argument():
    service = LLMAgentTaskFailureRecoveryService()

    with pytest.raises(InvalidAgentTaskFailureRecoveryExecutionError):
        service.execute_plan("not-a-plan")


def test_retry_without_scheduler_fails_explicitly():
    service = LLMAgentTaskFailureRecoveryService()

    result = service.execute_plan(_plan(RECOVERY_ACTION_RETRY))

    assert result.success is False
    assert result.executed_action is None
    assert "no retry scheduler" in result.failure_reason


# --- dependency recovery -------------------------------------------------------------------------


def test_dependency_recovery_enqueues_when_ready():
    queue_service = _FakeQueueService(priority=7)
    service = LLMAgentTaskFailureRecoveryService(
        readiness_service=_FakeReadinessService(ready=True), queue_service=queue_service
    )

    result = service.execute_plan(_plan(RECOVERY_ACTION_WAIT_FOR_DEPENDENCY))

    assert result.success is True
    assert queue_service.calls == 1
    assert "priority 7" in result.affected_reference


def test_dependency_recovery_still_blocked_fails_explicitly():
    service = LLMAgentTaskFailureRecoveryService(readiness_service=_FakeReadinessService(ready=False))

    result = service.execute_plan(_plan(RECOVERY_ACTION_WAIT_FOR_DEPENDENCY))

    assert result.success is False
    assert "still blocked" in result.failure_reason


def test_dependency_recovery_without_readiness_service_fails_explicitly():
    service = LLMAgentTaskFailureRecoveryService()

    result = service.execute_plan(_plan(RECOVERY_ACTION_WAIT_FOR_DEPENDENCY))

    assert result.success is False
    assert result.executed_action is None


# --- context recovery ----------------------------------------------------------------------------


def test_context_recovery_refreshes_successfully():
    service = LLMAgentTaskFailureRecoveryService(
        context_refresh_service=_FakeContextRefreshService(added=["source-1"], removed=[])
    )

    result = service.execute_plan(_plan(RECOVERY_ACTION_REFRESH_CONTEXT))

    assert result.success is True
    assert result.executed_action == RECOVERY_ACTION_REFRESH_CONTEXT
    assert "1 added" in result.affected_reference


def test_context_recovery_without_service_fails_explicitly():
    service = LLMAgentTaskFailureRecoveryService()

    result = service.execute_plan(_plan(RECOVERY_ACTION_REFRESH_CONTEXT))

    assert result.success is False


# --- task repair ------------------------------------------------------------------------------------


def test_task_repair_executes_a_real_repair_plan():
    repair_plan = RetryRepairPlan(
        tasks=["task-1"],
        schedules_to_create=[RepairOperation(task_id="task-1", operation=CREATE, reason="eligible again")],
    )
    scheduler = _FakeRetryScheduler(attempt=2)
    service = LLMAgentTaskFailureRecoveryService(
        retry_scheduler=scheduler, retry_repair_service=_FakeRetryRepairService(repair_plan)
    )

    result = service.execute_plan(_plan(RECOVERY_ACTION_REPAIR_TASK))

    assert result.success is True
    assert result.executed_action == RECOVERY_ACTION_REPAIR_TASK
    assert scheduler.calls == 1
    assert "SUCCESS" in result.affected_reference


def test_task_repair_without_services_fails_explicitly():
    service = LLMAgentTaskFailureRecoveryService()

    result = service.execute_plan(_plan(RECOVERY_ACTION_REPAIR_TASK))

    assert result.success is False
    assert result.executed_action is None


# --- unrecoverable failure --------------------------------------------------------------------------


def test_mark_unrecoverable_dead_letters_the_task():
    dead_letter_service = _FakeDeadLetterService()
    service = LLMAgentTaskFailureRecoveryService(dead_letter_service=dead_letter_service)

    result = service.execute_plan(_plan(RECOVERY_ACTION_MARK_UNRECOVERABLE, reason="task was cancelled"))

    assert result.success is True
    assert result.executed_action == RECOVERY_ACTION_MARK_UNRECOVERABLE
    assert "task was cancelled" in result.affected_reference


def test_mark_unrecoverable_without_service_fails_explicitly():
    service = LLMAgentTaskFailureRecoveryService()

    result = service.execute_plan(_plan(RECOVERY_ACTION_MARK_UNRECOVERABLE))

    assert result.success is False


# --- unsupported action -----------------------------------------------------------------------------


def test_unresolved_action_fails_explicitly_not_silently():
    service = LLMAgentTaskFailureRecoveryService()

    result = service.execute_plan(_plan(RECOVERY_ACTION_UNRESOLVED))

    assert result.success is False
    assert result.executed_action is None
    assert result.planned_action == RECOVERY_ACTION_UNRESOLVED


def test_no_action_needed_succeeds_trivially():
    service = LLMAgentTaskFailureRecoveryService()

    result = service.execute_plan(_plan(RECOVERY_ACTION_NONE))

    assert result.success is True
    assert result.executed_action == RECOVERY_ACTION_NONE


def test_completely_unknown_action_string_fails_explicitly():
    service = LLMAgentTaskFailureRecoveryService()

    result = service.execute_plan(_plan("some_made_up_action"))

    assert result.success is False
    assert result.executed_action is None


# --- underlying recovery failure ----------------------------------------------------------------------


def test_underlying_retry_failure_is_reported_not_raised():
    service = LLMAgentTaskFailureRecoveryService(
        retry_scheduler=_FakeRetryScheduler(error=RuntimeError("scheduler backend unavailable"))
    )

    result = service.execute_plan(_plan(RECOVERY_ACTION_RETRY))

    assert result.success is False
    assert result.executed_action == RECOVERY_ACTION_RETRY
    assert "scheduler backend unavailable" in result.failure_reason


def test_repair_failure_is_captured_and_reported():
    repair_plan = RetryRepairPlan(
        tasks=["task-1"],
        schedules_to_create=[RepairOperation(task_id="task-1", operation=CREATE, reason="eligible again")],
    )
    scheduler = _FakeRetryScheduler(error=IneligibleForRetryError("no longer eligible"))
    service = LLMAgentTaskFailureRecoveryService(
        retry_scheduler=scheduler, retry_repair_service=_FakeRetryRepairService(repair_plan)
    )

    result = service.execute_plan(_plan(RECOVERY_ACTION_REPAIR_TASK))

    assert result.success is False
    assert "FAILED" in result.failure_reason


# --- repeated / idempotent execution ------------------------------------------------------------------------


def test_repeated_retry_execution_is_idempotent_via_real_scheduler():
    scheduler = LLMAgentTaskRetryScheduler(eligibility_service=_FakeEligibilityService())
    service = LLMAgentTaskFailureRecoveryService(retry_scheduler=scheduler)
    plan = _plan(RECOVERY_ACTION_RETRY)

    first = service.execute_plan(plan)
    second = service.execute_plan(plan)

    assert first.success is True
    assert second.success is True
    assert first.affected_reference == second.affected_reference  # same schedule, not duplicated
    assert scheduler.get_retry_schedule("task-1").attempt == 1


def test_repeated_mark_unrecoverable_is_idempotent():
    dead_letter_service = _FakeDeadLetterService()
    service = LLMAgentTaskFailureRecoveryService(dead_letter_service=dead_letter_service)
    plan = _plan(RECOVERY_ACTION_MARK_UNRECOVERABLE, reason="cancelled")

    first = service.execute_plan(plan)
    second = service.execute_plan(plan)

    assert first.success is True
    assert second.success is True


# --- unrelated task state remains untouched --------------------------------------------------------------------


def test_unrelated_task_is_untouched_by_execution():
    scheduler = LLMAgentTaskRetryScheduler(eligibility_service=_FakeEligibilityService())
    service = LLMAgentTaskFailureRecoveryService(retry_scheduler=scheduler)

    service.execute_plan(_plan(RECOVERY_ACTION_RETRY, task_id="task-1"))

    assert scheduler.get_retry_schedule("task-2") is None
