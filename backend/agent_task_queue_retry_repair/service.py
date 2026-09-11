from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_queue import InvalidQueueEntryError
from backend.agent_task_queue_retry_reconciliation import LLMAgentTaskRetryReconciliationService
from backend.agent_task_queue_retry_scheduler import LLMAgentTaskRetryScheduler

from .models import BLOCKED, CANCEL, CREATE, UPDATE, RepairOperation, RetryRepairPlan


class LLMAgentTaskRetryRepairService:
    """Turns Commit #11's own reconciliation findings into a concrete,
    deterministic repair plan -- never a second retry engine or
    scheduler, and never the repair itself (Rule: "Do not create
    another retry engine or scheduler"; "Planning only -- no
    mutation"): plan_repair() never calls
    backend.agent_task_queue_retry_scheduler.LLMAgentTaskRetryScheduler.
    schedule_retry()/cancel_retry(), and never touches that scheduler's
    own store. It only reads Commit #11's own reconcile() and Commit
    #10's own resolve_eligibility(), and returns a RetryRepairPlan
    describing what a *separate* apply step could safely do (Behavior
    6).

    Behavior 1 ("Run existing reconciliation") is exactly Commit #11's
    own reconciliation_service.reconcile(task_id, now) -- this class
    invents no discrepancy detection of its own. Each of that result's
    own five buckets maps onto the minimal safe corrective operation
    for it (Behavior 2), reusing Commit #10's own
    scheduler.resolve_eligibility() (Behavior 3: "Revalidate retry
    eligibility before proposing a new schedule") to confirm each one
    is still accurate at plan_repair()'s own now, rather than trusting
    reconcile()'s own (already slightly earlier) snapshot blindly:

      - valid_schedules / due_schedules: preserved unchanged (Rule/
        Behavior 5) -- no operation of any kind, just counted into
        tasks.
      - stale_schedules: the attempt/eligible_at a fresh
        resolve_eligibility() call computes right now is proposed as
        an UPDATE to the existing schedule -- the minimal fix, never a
        cancel-and-recreate, since the schedule itself is still for a
        valid, eligible candidate, merely out of date. If re-validation
        itself now reports ineligible (the task's own state moved on
        again in between), this falls through to the same CANCEL/
        BLOCKED handling invalid_schedules gets, rather than proposing
        an update that is already wrong by the time it would be read.
      - invalid_schedules: always at least a CANCEL proposal (Rule 4:
        never a replacement CREATE for a completed/non-retryable/
        dead-lettered task) -- but when Commit #9's own
        RetryEligibilityResult.dead_letter_required reads True (attempts
        exhausted, or a non-retryable classification, and task_id is
        not already dead-lettered), this service will not silently
        decide "just cancel it" on task_id's behalf: whether to
        dead-letter it, extend its attempts, or something else entirely
        is a policy call outside this service's own remit, so it is
        reported as BLOCKED instead (Rule: "If a repair cannot be
        safely determined, report it as blocked"). An *already*
        dead-lettered or COMPLETED task's own stale schedule carries no
        such ambiguity (dead_letter_required already reads False for
        those -- see Commit #9's own RetryEligibilityResult docstring)
        and is simply CANCELled.
      - missing_schedules: the same dead_letter_required-aware split as
        invalid_schedules -- CREATE when still eligible, BLOCKED when
        not and dead_letter_required, otherwise (a transient "not
        ready" with nothing left to safely propose) no operation at
        all, never a fabricated one (Rule: "Never silently repair
        inconsistencies" cuts the other way here too: proposing a
        schedule this service cannot stand behind would itself be an
        unsafe, silent "repair").

    When task_id is given explicitly, it is always included in tasks
    even if nothing about it needs any operation at all -- a caller
    that asked about one task_id should always be able to tell "this
    was checked and found fine" apart from "this was never looked at."
    """

    def __init__(
        self,
        reconciliation_service: LLMAgentTaskRetryReconciliationService,
        scheduler: LLMAgentTaskRetryScheduler,
    ):
        """
        Args:
            reconciliation_service: The exact Commit #11
                LLMAgentTaskRetryReconciliationService instance --
                required, never defaulted.
            scheduler: The exact Commit #10 LLMAgentTaskRetryScheduler
                instance reconciliation_service itself reads schedules
                from -- required, so revalidation reads the same real
                eligibility state.
        """
        self._reconciliation_service = reconciliation_service
        self._scheduler = scheduler

    def plan_repair(self, task_id: str = None, now: Optional[datetime] = None) -> RetryRepairPlan:
        """Plan corrective operations for task_id's own schedule (and,
        only in that scoped mode, whether it is missing one it should
        have), or every currently SCHEDULED record when task_id is
        omitted -- exactly Commit #11's own reconcile() scoping rules.

        Raises:
            InvalidQueueEntryError: If task_id is given and is not a
                non-empty string, or now is given and is not a datetime
        """
        if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
            raise InvalidQueueEntryError("task_id must be a non-empty string when given")
        now = self._resolve_now(now)

        reconciliation = self._reconciliation_service.reconcile(task_id=task_id, now=now)

        tasks = set()
        if task_id is not None:
            tasks.add(task_id)

        schedule_updates, schedules_to_cancel, schedules_to_create, blocked_repairs = [], [], [], []

        for schedule in reconciliation.valid_schedules + reconciliation.due_schedules:
            tasks.add(schedule.task_id)

        for schedule in reconciliation.stale_schedules:
            tasks.add(schedule.task_id)
            eligibility = self._scheduler.resolve_eligibility(schedule.task_id, now=now)
            if eligibility.eligible:
                schedule_updates.append(
                    RepairOperation(
                        task_id=schedule.task_id,
                        operation=UPDATE,
                        reason=(
                            f"schedule attempt {schedule.attempt} no longer matches the current "
                            f"attempt {(eligibility.attempt_count or 0) + 1}"
                        ),
                        proposed_attempt=(eligibility.attempt_count or 0) + 1,
                        proposed_eligible_at=eligibility.next_eligible_at or now,
                    )
                )
            else:
                self._plan_cancel_or_block(schedule.task_id, eligibility, schedules_to_cancel, blocked_repairs)

        for schedule in reconciliation.invalid_schedules:
            tasks.add(schedule.task_id)
            eligibility = self._scheduler.resolve_eligibility(schedule.task_id, now=now)
            self._plan_cancel_or_block(schedule.task_id, eligibility, schedules_to_cancel, blocked_repairs)

        for missing_task_id in reconciliation.missing_schedules:
            tasks.add(missing_task_id)
            eligibility = self._scheduler.resolve_eligibility(missing_task_id, now=now)
            if eligibility.eligible:
                schedules_to_create.append(
                    RepairOperation(
                        task_id=missing_task_id,
                        operation=CREATE,
                        reason=eligibility.reason,
                        proposed_attempt=(eligibility.attempt_count or 0) + 1,
                        proposed_eligible_at=eligibility.next_eligible_at or now,
                    )
                )
            elif eligibility.dead_letter_required:
                blocked_repairs.append(
                    RepairOperation(
                        task_id=missing_task_id,
                        operation=BLOCKED,
                        reason=f"cannot safely schedule a retry: {eligibility.reason}",
                    )
                )
            # else: no longer eligible for a reason that needs no
            # decision (e.g. transiently not ready) -- nothing to
            # propose, and proposing anything here would itself be an
            # invented, unsafe "repair."

        summary = (
            f"{len(schedule_updates)} update(s), {len(schedules_to_cancel)} cancellation(s), "
            f"{len(schedules_to_create)} creation(s), {len(blocked_repairs)} blocked"
        )

        return RetryRepairPlan(
            tasks=sorted(tasks),
            schedule_updates=schedule_updates,
            schedules_to_cancel=schedules_to_cancel,
            schedules_to_create=schedules_to_create,
            blocked_repairs=blocked_repairs,
            summary=summary,
        )

    @staticmethod
    def _plan_cancel_or_block(task_id: str, eligibility, schedules_to_cancel: list, blocked_repairs: list) -> None:
        if eligibility.dead_letter_required:
            blocked_repairs.append(
                RepairOperation(
                    task_id=task_id,
                    operation=BLOCKED,
                    reason=f"cannot safely determine repair: {eligibility.reason}",
                )
            )
            return
        schedules_to_cancel.append(
            RepairOperation(
                task_id=task_id,
                operation=CANCEL,
                reason=f"task is no longer a valid retry candidate: {eligibility.reason}",
            )
        )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidQueueEntryError("now must be a datetime when given")
        return now
