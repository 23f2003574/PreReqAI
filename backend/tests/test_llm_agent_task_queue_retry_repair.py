from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_lifecycle import PLANNED, READY, LLMAgentTaskLifecycleService
from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
from backend.agent_task_queue_retry_reconciliation import LLMAgentTaskRetryReconciliationService
from backend.agent_task_queue_retry_repair import (
    BLOCKED,
    CANCEL,
    CREATE,
    UPDATE,
    LLMAgentTaskRetryRepairService,
)
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
    repair_service = LLMAgentTaskRetryRepairService(reconciliation_service, scheduler)
    return lifecycle_service, queue_service, dead_letter_service, scheduler, repair_service


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestStaleScheduleRepair:
    def test_stale_schedule_produces_update(self):
        lifecycle_service, _, _, scheduler, repair_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=1, max_attempts=5)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)
        assert schedule.attempt == 2

        stale = replace(schedule, attempt=9)
        scheduler.store.save(stale)

        plan = repair_service.plan_repair(task_id=task.task_id, now=NOW)

        assert len(plan.schedule_updates) == 1
        update = plan.schedule_updates[0]
        assert update.task_id == task.task_id
        assert update.operation == UPDATE
        assert update.proposed_attempt == 2
        assert update.reason
        assert plan.schedules_to_cancel == []
        assert plan.schedules_to_create == []


class TestMissingEligibleScheduleRepair:
    def test_missing_schedule_produces_create(self):
        lifecycle_service, *_, repair_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)

        plan = repair_service.plan_repair(task_id=task.task_id, now=NOW)

        assert len(plan.schedules_to_create) == 1
        create = plan.schedules_to_create[0]
        assert create.task_id == task.task_id
        assert create.operation == CREATE
        assert create.proposed_attempt == 1
        assert create.reason
        assert plan.schedule_updates == []
        assert plan.schedules_to_cancel == []
        assert plan.blocked_repairs == []


class TestValidScheduleNoOperation:
    def test_valid_schedule_produces_no_operation(self):
        lifecycle_service, _, _, scheduler, repair_service = _services()
        task = _ready_task(lifecycle_service, next_eligible_at=NOW + timedelta(hours=1))
        scheduler.schedule_retry(task.task_id, now=NOW)

        plan = repair_service.plan_repair(task_id=task.task_id, now=NOW)

        assert plan.tasks == [task.task_id]
        assert plan.schedule_updates == []
        assert plan.schedules_to_cancel == []
        assert plan.schedules_to_create == []
        assert plan.blocked_repairs == []
        assert "0 update" in plan.summary


class TestIneligibleTaskBlockedOrNoCreation:
    def test_ineligible_task_without_schedule_produces_no_creation(self):
        lifecycle_service, *_, repair_service = _services()
        task = _ready_task(lifecycle_service, retryable=False)

        plan = repair_service.plan_repair(task_id=task.task_id, now=NOW)

        assert plan.schedules_to_create == []
        assert plan.tasks == [task.task_id]

    def test_retry_limit_exhausted_schedule_is_blocked_not_silently_cancelled(self):
        lifecycle_service, _, dead_letter_service, scheduler, repair_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=2, max_attempts=3)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)
        assert schedule.attempt == 3

        # Directly age the schedule's own attempt forward to simulate a
        # further failure that exhausted the retry limit (attempt_count
        # is fixed on the task's own definition in this repository, so
        # the schedule itself is what carries the "already at the
        # limit" state a fresh eligibility check would now compute).
        exhausted = _ready_task(lifecycle_service, attempt_count=3, max_attempts=3)
        exhausted_schedule = replace(schedule, task_id=exhausted.task_id, attempt=3)
        scheduler.store.save(exhausted_schedule)

        plan = repair_service.plan_repair(task_id=exhausted.task_id, now=NOW)

        assert plan.schedules_to_cancel == []
        assert plan.schedules_to_create == []
        assert len(plan.blocked_repairs) == 1
        blocked = plan.blocked_repairs[0]
        assert blocked.task_id == exhausted.task_id
        assert blocked.operation == BLOCKED
        assert blocked.reason

    def test_already_dead_lettered_stale_schedule_is_cancelled_not_blocked(self):
        lifecycle_service, queue_service, dead_letter_service, scheduler, repair_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)
        queue_service.enqueue(task.task_id)
        dead_letter_service.dead_letter(task.task_id, "manually excluded")

        plan = repair_service.plan_repair(task_id=task.task_id, now=NOW)

        assert len(plan.schedules_to_cancel) == 1
        assert plan.schedules_to_cancel[0].task_id == task.task_id
        assert plan.schedules_to_cancel[0].operation == CANCEL
        assert plan.blocked_repairs == []
        assert schedule is not None


class TestMultipleDiscrepanciesCompletePlan:
    def test_mixed_findings_produce_complete_plan(self):
        lifecycle_service, queue_service, dead_letter_service, scheduler, repair_service = _services()

        valid_task = _ready_task(lifecycle_service, next_eligible_at=NOW + timedelta(hours=1))
        scheduler.schedule_retry(valid_task.task_id, now=NOW)

        stale_task = _ready_task(lifecycle_service, attempt_count=1, max_attempts=5)
        stale_schedule = scheduler.schedule_retry(stale_task.task_id, now=NOW)
        scheduler.store.save(replace(stale_schedule, attempt=8))

        dead_task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(dead_task.task_id, now=NOW)
        queue_service.enqueue(dead_task.task_id)
        dead_letter_service.dead_letter(dead_task.task_id, "excluded")

        missing_task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)

        plan = repair_service.plan_repair(now=NOW)  # full sweep

        assert {op.task_id for op in plan.schedule_updates} == {stale_task.task_id}
        assert {op.task_id for op in plan.schedules_to_cancel} == {dead_task.task_id}
        assert valid_task.task_id in plan.tasks
        # missing_task is never surfaced in a full sweep (Commit #11's
        # own scoping rule -- see that module's own docstring).
        assert missing_task.task_id not in plan.tasks


class TestRepeatedPlanningDeterministic:
    def test_repeated_calls_produce_identical_plan(self):
        lifecycle_service, _, _, scheduler, repair_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=1, max_attempts=5)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)
        scheduler.store.save(replace(schedule, attempt=8))

        first = repair_service.plan_repair(task_id=task.task_id, now=NOW)
        second = repair_service.plan_repair(task_id=task.task_id, now=NOW)

        assert first == second


class TestNoPersistenceMutation:
    def test_plan_repair_never_mutates_schedule_store(self):
        lifecycle_service, _, _, scheduler, repair_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=1, max_attempts=5)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)
        stale = replace(schedule, attempt=8)
        scheduler.store.save(stale)

        repair_service.plan_repair(task_id=task.task_id, now=NOW)

        assert scheduler.get_retry_schedule(task.task_id) == stale

    def test_plan_repair_never_creates_or_cancels(self):
        lifecycle_service, queue_service, dead_letter_service, scheduler, repair_service = _services()
        missing_task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        dead_task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(dead_task.task_id, now=NOW)
        queue_service.enqueue(dead_task.task_id)
        dead_letter_service.dead_letter(dead_task.task_id, "excluded")

        repair_service.plan_repair(task_id=missing_task.task_id, now=NOW)
        repair_service.plan_repair(task_id=dead_task.task_id, now=NOW)

        assert scheduler.get_retry_schedule(missing_task.task_id) is None
        assert scheduler.get_retry_schedule(dead_task.task_id) is not None
        assert scheduler.get_retry_schedule(dead_task.task_id).status == "SCHEDULED"


class TestInvalidInput:
    def test_plan_repair_rejects_blank_task_id(self):
        *_, repair_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            repair_service.plan_repair(task_id="")

    def test_plan_repair_rejects_non_datetime_now(self):
        *_, repair_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            repair_service.plan_repair(now="not-a-datetime")
