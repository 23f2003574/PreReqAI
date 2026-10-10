from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_lifecycle import COMPLETED, PLANNED, READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
from backend.agent_task_queue_retry_reconciliation import LLMAgentTaskRetryReconciliationService
from backend.agent_task_queue_retry_scheduler import LLMAgentTaskRetryScheduler
from backend.agent_task_readiness import LLMAgentTaskReadinessService

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services():
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    dead_letter_service = LLMAgentTaskDeadLetterService(queue_service, lifecycle_service)
    eligibility_service = LLMAgentTaskQueueRetryEligibilityService(
        lifecycle_service, readiness_service, dead_letter_service
    )
    scheduler = LLMAgentTaskRetryScheduler(eligibility_service)
    reconciliation_service = LLMAgentTaskRetryReconciliationService(lifecycle_service, dead_letter_service, scheduler)
    return lifecycle_service, queue_service, dead_letter_service, scheduler, reconciliation_service


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestValidScheduleRemainsValid:
    def test_not_yet_due_schedule_is_valid(self):
        lifecycle_service, _, _, scheduler, reconciliation_service = _services()
        task = _ready_task(lifecycle_service, next_eligible_at=NOW + timedelta(hours=1))
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)

        result = reconciliation_service.reconcile(task_id=task.task_id, now=NOW)

        assert result.valid_schedules == [schedule]
        assert result.due_schedules == []
        assert result.stale_schedules == []
        assert result.invalid_schedules == []
        assert result.missing_schedules == []


class TestDueScheduleDetected:
    def test_elapsed_schedule_is_due(self):
        lifecycle_service, _, _, scheduler, reconciliation_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)

        result = reconciliation_service.reconcile(task_id=task.task_id, now=NOW)

        assert result.due_schedules == [schedule]
        assert result.valid_schedules == []
        assert any("due" in action for action in result.actions_required)


class TestCompletedTaskInvalid:
    def test_completed_task_schedule_is_invalid(self):
        lifecycle_service, _, _, scheduler, reconciliation_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)

        lifecycle_service.transition(task.task_id, RUNNING)
        lifecycle_service.transition(task.task_id, COMPLETED)

        result = reconciliation_service.reconcile(task_id=task.task_id, now=NOW)

        assert result.invalid_schedules == [schedule]
        assert result.valid_schedules == []
        assert result.due_schedules == []


class TestAttemptMismatchDetected:
    def test_stale_attempt_number_is_detected(self):
        lifecycle_service, _, _, scheduler, reconciliation_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=1, max_attempts=5)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)
        assert schedule.attempt == 2

        # Simulate the task having been attempted again since this
        # schedule was made (AgentTask.definition is immutable once
        # created in this repository, so this is injected directly
        # into the scheduler's own store rather than by mutating the
        # task) -- the schedule now claims attempt 5, but current
        # eligibility still expects attempt 2.
        stale = replace(schedule, attempt=5)
        scheduler.store.save(stale)

        result = reconciliation_service.reconcile(task_id=task.task_id, now=NOW)

        assert result.stale_schedules == [stale]
        assert result.valid_schedules == []
        assert result.due_schedules == []
        assert any("stale" in action for action in result.actions_required)


class TestDeadLetteredTaskDetected:
    def test_dead_lettered_task_schedule_is_invalid(self):
        lifecycle_service, queue_service, dead_letter_service, scheduler, reconciliation_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)
        queue_service.enqueue(task.task_id)
        dead_letter_service.dead_letter(task.task_id, "manually excluded")

        result = reconciliation_service.reconcile(task_id=task.task_id, now=NOW)

        assert result.invalid_schedules == [schedule]


class TestMissingExpectedScheduleDetected:
    def test_eligible_task_without_schedule_is_missing(self):
        lifecycle_service, _, _, scheduler, reconciliation_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)

        result = reconciliation_service.reconcile(task_id=task.task_id, now=NOW)

        assert result.missing_schedules == [task.task_id]
        assert any("missing" in action.lower() or "eligible but has no schedule" in action
                   for action in result.actions_required)

    def test_ineligible_task_without_schedule_is_not_missing(self):
        lifecycle_service, *_, reconciliation_service = _services()
        task = _ready_task(lifecycle_service, retryable=False)

        result = reconciliation_service.reconcile(task_id=task.task_id, now=NOW)

        assert result.missing_schedules == []

    def test_sweep_mode_never_reports_missing(self):
        lifecycle_service, *_, reconciliation_service = _services()
        _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)  # never scheduled

        result = reconciliation_service.reconcile(now=NOW)  # task_id=None, full sweep

        assert result.missing_schedules == []


class TestMultipleTasksIsolated:
    def test_sweep_isolates_findings_per_task(self):
        lifecycle_service, _, _, scheduler, reconciliation_service = _services()
        valid_task = _ready_task(lifecycle_service, next_eligible_at=NOW + timedelta(hours=1))
        due_task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        stale_task = _ready_task(lifecycle_service, attempt_count=1, max_attempts=5)

        valid_schedule = scheduler.schedule_retry(valid_task.task_id, now=NOW)
        due_schedule = scheduler.schedule_retry(due_task.task_id, now=NOW)
        stale_schedule = scheduler.schedule_retry(stale_task.task_id, now=NOW)
        scheduler.store.save(replace(stale_schedule, attempt=9))

        result = reconciliation_service.reconcile(now=NOW)

        assert {s.task_id for s in result.valid_schedules} == {valid_task.task_id}
        assert {s.task_id for s in result.due_schedules} == {due_task.task_id}
        assert {s.task_id for s in result.stale_schedules} == {stale_task.task_id}


class TestRepeatedReconciliationDeterministic:
    def test_repeated_calls_produce_identical_result(self):
        lifecycle_service, _, _, scheduler, reconciliation_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(task.task_id, now=NOW)

        first = reconciliation_service.reconcile(task_id=task.task_id, now=NOW)
        second = reconciliation_service.reconcile(task_id=task.task_id, now=NOW)

        assert first == second

    def test_repeated_sweep_produces_identical_result(self):
        lifecycle_service, _, _, scheduler, reconciliation_service = _services()
        for _ in range(3):
            task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
            scheduler.schedule_retry(task.task_id, now=NOW)

        first = reconciliation_service.reconcile(now=NOW)
        second = reconciliation_service.reconcile(now=NOW)

        assert first == second


class TestReadOnly:
    def test_reconcile_never_mutates_schedule_store(self):
        lifecycle_service, _, _, scheduler, reconciliation_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        before = scheduler.schedule_retry(task.task_id, now=NOW)

        reconciliation_service.reconcile(task_id=task.task_id, now=NOW)

        assert scheduler.get_retry_schedule(task.task_id) == before

    def test_reconcile_never_enqueues(self):
        lifecycle_service, queue_service, _, scheduler, reconciliation_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(task.task_id, now=NOW)

        reconciliation_service.reconcile(task_id=task.task_id, now=NOW)

        assert queue_service.contains(task.task_id) is False


class TestInvalidInput:
    def test_reconcile_rejects_blank_task_id(self):
        *_, reconciliation_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            reconciliation_service.reconcile(task_id="")

    def test_reconcile_rejects_non_datetime_now(self):
        *_, reconciliation_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            reconciliation_service.reconcile(now="not-a-datetime")
