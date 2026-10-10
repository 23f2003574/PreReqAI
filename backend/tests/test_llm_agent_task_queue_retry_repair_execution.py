from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_lifecycle import PLANNED, READY, LLMAgentTaskLifecycleService
from backend.agent_task_queue import LLMAgentTaskQueueService
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
from backend.agent_task_queue_retry_reconciliation import LLMAgentTaskRetryReconciliationService
from backend.agent_task_queue_retry_repair import (
    LLMAgentTaskRetryRepairService,
    RepairOperation,
    RetryRepairPlan,
)
from backend.agent_task_queue_retry_repair import CANCEL as OP_CANCEL
from backend.agent_task_queue_retry_repair import CREATE as OP_CREATE
from backend.agent_task_queue_retry_repair_execution import (
    FAILED,
    NO_OP,
    PARTIAL,
    SUCCESS,
    InvalidRetryRepairPlanError,
    LLMAgentTaskRetryRepairExecutor,
)
from backend.agent_task_queue_retry_scheduler import CANCELLED, SCHEDULED, LLMAgentTaskRetryScheduler
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
    executor = LLMAgentTaskRetryRepairExecutor(scheduler)
    return lifecycle_service, queue_service, dead_letter_service, scheduler, repair_service, executor


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestValidRepairPlanAppliesCorrectly:
    def test_mixed_plan_applies_every_operation(self):
        lifecycle_service, queue_service, dead_letter_service, scheduler, repair_service, executor = _services()

        stale_task = _ready_task(lifecycle_service, attempt_count=1, max_attempts=5)
        stale_schedule = scheduler.schedule_retry(stale_task.task_id)
        scheduler.store.save(replace(stale_schedule, attempt=9))

        dead_task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(dead_task.task_id)
        queue_service.enqueue(dead_task.task_id)
        dead_letter_service.dead_letter(dead_task.task_id, "excluded")

        missing_task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)

        plan = repair_service.plan_repair(now=NOW)
        # missing_task never surfaces in a full sweep (Commit #11/#12's
        # own scoping) -- plan it explicitly too and merge by hand to
        # exercise a CREATE as part of the same apply() call.
        missing_plan = repair_service.plan_repair(task_id=missing_task.task_id, now=NOW)
        full_plan = replace(
            plan, schedules_to_create=plan.schedules_to_create + missing_plan.schedules_to_create
        )

        result = executor.apply(full_plan)

        assert result.final_status == SUCCESS
        assert len(result.applied_operations) == 3
        assert result.failed_operations == []
        assert result.skipped_operations == []

        assert scheduler.get_retry_schedule(stale_task.task_id).attempt == 2
        assert scheduler.get_retry_schedule(dead_task.task_id).status == CANCELLED
        assert scheduler.get_retry_schedule(missing_task.task_id).status == SCHEDULED


class TestStaleScheduleCorrectionWorks:
    def test_update_operation_corrects_attempt_in_place(self):
        lifecycle_service, _, _, scheduler, repair_service, executor = _services()
        task = _ready_task(lifecycle_service, attempt_count=1, max_attempts=5)
        schedule = scheduler.schedule_retry(task.task_id)
        scheduler.store.save(replace(schedule, attempt=9))

        plan = repair_service.plan_repair(task_id=task.task_id, now=NOW)
        result = executor.apply(plan)

        assert result.final_status == SUCCESS
        corrected = scheduler.get_retry_schedule(task.task_id)
        assert corrected.attempt == 2
        assert corrected.status == SCHEDULED

    def test_cancel_operation_actually_cancels(self):
        lifecycle_service, queue_service, dead_letter_service, scheduler, repair_service, executor = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(task.task_id)
        queue_service.enqueue(task.task_id)
        dead_letter_service.dead_letter(task.task_id, "excluded")

        plan = repair_service.plan_repair(task_id=task.task_id, now=NOW)
        result = executor.apply(plan)

        assert result.final_status == SUCCESS
        assert scheduler.get_retry_schedule(task.task_id).status == CANCELLED


class TestMissingEligibleScheduleCreationWorks:
    def test_create_operation_actually_schedules(self):
        lifecycle_service, _, _, scheduler, repair_service, executor = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        assert scheduler.get_retry_schedule(task.task_id) is None

        plan = repair_service.plan_repair(task_id=task.task_id, now=NOW)
        result = executor.apply(plan)

        assert result.final_status == SUCCESS
        created = scheduler.get_retry_schedule(task.task_id)
        assert created is not None
        assert created.status == SCHEDULED
        assert created.attempt == 1


class TestIneligibleCreationRejectedAfterRevalidation:
    def test_create_op_for_now_dead_lettered_task_fails(self):
        lifecycle_service, queue_service, dead_letter_service, scheduler, repair_service, executor = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)

        # A CREATE proposal computed before the task was dead-lettered
        # (hand-built, standing in for a plan applied some time after
        # it was made -- exactly the scenario Behavior 2's own
        # revalidation exists for).
        stale_create = RepairOperation(task_id=task.task_id, operation=OP_CREATE, reason="eligible for retry")
        plan = RetryRepairPlan(tasks=[task.task_id], schedules_to_create=[stale_create])

        queue_service.enqueue(task.task_id)
        dead_letter_service.dead_letter(task.task_id, "excluded after plan was made")

        result = executor.apply(plan)

        assert result.final_status == FAILED
        assert result.applied_operations == []
        assert len(result.failed_operations) == 1
        failed_op, error = result.failed_operations[0]
        assert failed_op.task_id == task.task_id
        assert scheduler.get_retry_schedule(task.task_id) is None


class TestAlreadyAppliedRepairIsIdempotent:
    def test_reapplying_the_same_plan_is_safe(self):
        lifecycle_service, _, _, scheduler, repair_service, executor = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)

        plan = repair_service.plan_repair(task_id=task.task_id, now=NOW)
        first = executor.apply(plan)
        second = executor.apply(plan)

        assert first.final_status == SUCCESS
        assert second.final_status == SUCCESS
        assert second.failed_operations == []
        assert scheduler.get_retry_schedule(task.task_id).attempt == 1

    def test_reapplying_a_cancel_is_safe(self):
        lifecycle_service, queue_service, dead_letter_service, scheduler, repair_service, executor = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(task.task_id)
        queue_service.enqueue(task.task_id)
        dead_letter_service.dead_letter(task.task_id, "excluded")

        plan = repair_service.plan_repair(task_id=task.task_id, now=NOW)
        executor.apply(plan)
        second = executor.apply(plan)

        assert second.failed_operations == []
        assert scheduler.get_retry_schedule(task.task_id).status == CANCELLED


class TestPartialFailureReportedCorrectly:
    def test_one_failure_does_not_hide_other_successes(self):
        lifecycle_service, queue_service, dead_letter_service, scheduler, repair_service, executor = _services()

        good_task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        bad_task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)

        good_create = RepairOperation(task_id=good_task.task_id, operation=OP_CREATE, reason="eligible for retry")
        bad_create = RepairOperation(task_id=bad_task.task_id, operation=OP_CREATE, reason="eligible for retry")
        plan = RetryRepairPlan(
            tasks=[good_task.task_id, bad_task.task_id], schedules_to_create=[good_create, bad_create]
        )

        queue_service.enqueue(bad_task.task_id)
        dead_letter_service.dead_letter(bad_task.task_id, "excluded before apply")

        result = executor.apply(plan)

        assert result.final_status == PARTIAL
        assert [op.task_id for op in result.applied_operations] == [good_task.task_id]
        assert len(result.failed_operations) == 1
        assert result.failed_operations[0][0].task_id == bad_task.task_id
        assert scheduler.get_retry_schedule(good_task.task_id).status == SCHEDULED
        assert scheduler.get_retry_schedule(bad_task.task_id) is None


class TestValidUnrelatedSchedulesRemainUntouched:
    def test_unrelated_valid_schedule_is_not_in_plan_or_touched(self):
        lifecycle_service, _, _, scheduler, repair_service, executor = _services()
        unrelated = _ready_task(lifecycle_service, next_eligible_at=NOW + timedelta(hours=1))
        unrelated_schedule = scheduler.schedule_retry(unrelated.task_id, now=NOW)

        stale_task = _ready_task(lifecycle_service, attempt_count=1, max_attempts=5)
        stale_schedule = scheduler.schedule_retry(stale_task.task_id, now=NOW)
        scheduler.store.save(replace(stale_schedule, attempt=9))

        plan = repair_service.plan_repair(now=NOW)
        assert unrelated.task_id not in [op.task_id for op in plan.schedule_updates]
        assert unrelated.task_id not in [op.task_id for op in plan.schedules_to_cancel]

        executor.apply(plan)

        assert scheduler.get_retry_schedule(unrelated.task_id) == unrelated_schedule


class TestBlockedRepairsSkipped:
    def test_blocked_entries_are_never_executed(self):
        lifecycle_service, _, _, scheduler, repair_service, executor = _services()
        task = _ready_task(lifecycle_service, attempt_count=2, max_attempts=3)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)
        # Force it to look already-at-the-limit, so reconciliation
        # classifies it invalid and repair reports it BLOCKED (Commit
        # #9's own dead_letter_required signal), not cancellable.
        exhausted = _ready_task(lifecycle_service, attempt_count=3, max_attempts=3)
        scheduler.store.save(replace(schedule, task_id=exhausted.task_id, attempt=3))

        plan = repair_service.plan_repair(task_id=exhausted.task_id, now=NOW)
        assert len(plan.blocked_repairs) == 1

        result = executor.apply(plan)

        assert result.final_status == NO_OP
        assert result.applied_operations == []
        assert result.failed_operations == []
        assert result.skipped_operations == plan.blocked_repairs
        assert scheduler.get_retry_schedule(exhausted.task_id).attempt == 3  # untouched


class TestInvalidInput:
    def test_apply_rejects_non_plan(self):
        *_, executor = _services()
        with pytest.raises(InvalidRetryRepairPlanError):
            executor.apply("not-a-plan")

    def test_empty_plan_is_no_op(self):
        *_, repair_service, executor = _services()
        result = executor.apply(RetryRepairPlan())

        assert result.final_status == NO_OP
        assert result.applied_operations == []
        assert result.skipped_operations == []
        assert result.failed_operations == []
