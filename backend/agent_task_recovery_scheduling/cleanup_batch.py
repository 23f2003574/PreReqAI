from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .cleanup import LLMAgentTaskRecoveryPreflightScheduleCleanupService
from .cleanup_batch_plan import (
    AgentTaskRecoveryScheduleCleanupBatchPlan,
    LLMAgentTaskRecoveryPreflightScheduleCleanupBatchPlanService,
)

BATCH_CLEANED = "cleaned"
BATCH_SKIPPED = "skipped"
BATCH_FAILED = "failed"


class InvalidAgentTaskRecoveryScheduleCleanupBatchError(ValueError):
    """Raised when execute() is given invalid arguments, or a plan that
    belongs to a different task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupBatchEntry:
    """One planned schedule's outcome: BATCH_CLEANED (with the terminal
    `reason` it was cleaned for), BATCH_SKIPPED (no longer eligible when
    reached -- already cleaned, dispatched, or active), or BATCH_FAILED
    (with the `error` text)."""

    schedule_id: str
    outcome: str
    reason: Optional[str]
    error: Optional[str]


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupBatchResult:
    """execute()'s per-schedule outcomes, in plan order, plus counts."""

    task_id: str
    executed_at: datetime
    entries: tuple
    cleaned_count: int
    skipped_count: int
    failed_count: int


class LLMAgentTaskRecoveryPreflightScheduleCleanupBatchService:
    """Applies the existing single-schedule cleanup to an ordered batch
    plan -- never a second cleanup engine: the only write is the cleanup
    service's own clean_schedule(), which makes the same eligibility
    decision and the same idempotent cancel() as a full cleanup() pass.

    Every planned schedule is re-evaluated by clean_schedule() at
    execution time, so a stale or hand-built plan can never touch a
    schedule that is active, dispatched or already cleaned (those come
    back BATCH_SKIPPED). Each schedule is processed independently: one
    that raises is recorded BATCH_FAILED and the rest still run, keeping
    every successful cleanup. History is preserved (a cleaned schedule
    is only ever cancelled, first reason/timestamp standing), so running
    the same plan again cleans nothing further. Never executes recovery
    or reschedules.
    """

    def __init__(
        self,
        plan_service: LLMAgentTaskRecoveryPreflightScheduleCleanupBatchPlanService = None,
        cleanup_service: LLMAgentTaskRecoveryPreflightScheduleCleanupService = None,
    ):
        """
        Args:
            plan_service/cleanup_service: Default to fresh services;
                wire both over the same scheduling/dispatch services so
                they see the same records.
        """
        self._plan_service = (
            plan_service if plan_service is not None else LLMAgentTaskRecoveryPreflightScheduleCleanupBatchPlanService()
        )
        self._cleanup_service = (
            cleanup_service if cleanup_service is not None else LLMAgentTaskRecoveryPreflightScheduleCleanupService()
        )

    def execute(
        self, task_id: str, plan: AgentTaskRecoveryScheduleCleanupBatchPlan = None, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleCleanupBatchResult:
        """Clean task_id's planned schedules, in plan order. Plans
        fresh from the plan service when plan is None.

        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupBatchError: If
                task_id is not a non-empty string, now is given and is
                not a datetime, or plan is given and is not a batch plan
                for task_id
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryScheduleCleanupBatchError(
                "task_id is required and must be a non-empty string"
            )
        if now is None:
            now = datetime.now(timezone.utc)
        elif not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleCleanupBatchError("now must be a datetime when given")

        if plan is None:
            plan = self._plan_service.plan(task_id, now=now)
        elif not isinstance(plan, AgentTaskRecoveryScheduleCleanupBatchPlan):
            raise InvalidAgentTaskRecoveryScheduleCleanupBatchError(
                "plan must be an AgentTaskRecoveryScheduleCleanupBatchPlan"
            )
        elif plan.task_id != task_id:
            raise InvalidAgentTaskRecoveryScheduleCleanupBatchError(
                f"plan belongs to task_id {plan.task_id!r}, not {task_id!r}"
            )

        entries = []
        for schedule_id in plan.schedule_ids:
            try:
                reason = self._cleanup_service.clean_schedule(task_id, schedule_id, now=now)
            except Exception as error:
                entries.append(AgentTaskRecoveryScheduleCleanupBatchEntry(schedule_id, BATCH_FAILED, None, str(error)))
                continue
            outcome = BATCH_CLEANED if reason is not None else BATCH_SKIPPED
            entries.append(AgentTaskRecoveryScheduleCleanupBatchEntry(schedule_id, outcome, reason, None))

        def count(outcome):
            return sum(1 for entry in entries if entry.outcome == outcome)

        return AgentTaskRecoveryScheduleCleanupBatchResult(
            task_id=task_id, executed_at=now, entries=tuple(entries), cleaned_count=count(BATCH_CLEANED),
            skipped_count=count(BATCH_SKIPPED), failed_count=count(BATCH_FAILED),
        )
