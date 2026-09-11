from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_lifecycle import COMPLETED, LLMAgentTaskLifecycleService, UnknownAgentTaskError
from backend.agent_task_queue import InvalidQueueEntryError
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_queue_retry_scheduler import SCHEDULED, LLMAgentTaskRetryScheduler

from .models import RetryReconciliationResult


class LLMAgentTaskRetryReconciliationService:
    """Compares Commit #10's own persisted TaskRetrySchedule records
    against current task/eligibility state and reports drift -- never a
    second scheduler or retry engine (Rule: "Do not create another
    scheduler or retry engine"): reconcile() never calls
    LLMAgentTaskRetryScheduler.schedule_retry()/cancel_retry(), never
    calls backend.agent_task_queue.LLMAgentTaskQueueService.enqueue(),
    and never mutates a schedule's own store (Rule: "Read-only
    analysis"). It only reads three already-existing stores/services
    and reports what it finds.

    Every check reuses an existing service, never a second copy of its
    logic (Rule: "Reuse existing retry scheduling and eligibility
    semantics"):
      - "current task lifecycle/failure/attempt state" (Behavior 2):
        Commit #1's own lifecycle_service.get().
      - "existing retry eligibility checks" (Behavior 3): Commit #10's
        own scheduler.resolve_eligibility() -- the exact same backoff-
        aware resolution schedule_retry() itself uses (see that
        method's own docstring for why a raw Commit #9 check() alone
        cannot answer "is this schedule still correct" either: a
        schedule waiting out its own backoff window must not read as
        "invalid" merely because Commit #9's own check() calls that
        ineligible).
      - dead-letter status: Commit #8's own dead_letter_service.get().

    Classification per schedule (Behavior 4, "attempt, status, timing,
    or eligibility"):
      - INVALID: task_id no longer exists, is dead-lettered, has
        reached COMPLETED, or resolve_eligibility() now reports
        ineligible for a reason other than backoff timing (Rule: "Treat
        dead-lettered/completed tasks as invalid retry candidates").
        The explicit COMPLETED/dead-letter checks are not strictly
        needed for correctness alone -- Commit #1's own readiness check
        already reports a COMPLETED task as not ready, and Commit #9's
        own check() already treats dead-letter status as ineligible on
        its own -- but naming them directly here gives a caller a much
        more specific, actionable reason than a generic "not ready"
        would, and matches this Rule's own explicit wording.
      - STALE: task_id is still a legitimate candidate and still
        eligible, but this schedule's own attempt no longer matches
        (attempt_count + 1) as freshly computed -- task_id was
        attempted again since this schedule was made, so the schedule
        itself is superseded ("timing" drift is not checked
        separately: in this repository, AgentTask.definition -- the
        only source Commit #9 ever reads attempt/backoff metadata
        from -- is fixed at create() time and never updated afterward,
        so eligible_at can only ever drift for the same underlying
        reason attempt does).
      - DUE: still correct, and its own eligible_at has already passed.
      - VALID: still correct, not yet due.
      Only currently-SCHEDULED records are ever classified this way --
      an already-CANCELLED one is treated exactly like "no live
      schedule" (see missing_schedules below), never reported as its
      own separate finding.

    missing_schedules (Behavior 5) is deliberately only ever populated
    when reconcile() is scoped to one specific task_id, not during a
    full sweep (task_id=None): backend.agent_task_lifecycle.
    LLMAgentTaskLifecycleService exposes no way to enumerate every
    AgentTask that has ever been created (only get() by a known
    task_id), so there is no sound way to ask "which task_ids, out of
    every task_id that has ever existed, currently lack a schedule they
    should have" during an unscoped sweep -- only "does *this* task_id
    have one." A full sweep still validates every schedule that *does*
    exist (into valid/due/stale/invalid); it simply cannot also report
    what it structurally has no way to discover.

    Deterministic for a supplied now (Rule): every comparison here uses
    exactly the now passed to (or defaulted once, at the top of) the
    call.
    """

    def __init__(
        self,
        lifecycle_service: LLMAgentTaskLifecycleService,
        dead_letter_service: LLMAgentTaskDeadLetterService,
        scheduler: LLMAgentTaskRetryScheduler,
    ):
        """
        Args:
            lifecycle_service: The exact Commit #1
                LLMAgentTaskLifecycleService instance holding task_ids'
                own AgentTask records -- required, never defaulted.
            dead_letter_service: The exact Commit #8
                LLMAgentTaskDeadLetterService instance -- required.
            scheduler: The exact Commit #10 LLMAgentTaskRetryScheduler
                instance holding the persisted schedules reconciled --
                required, so both the schedules read and the
                eligibility resolution reused are the real ones.
        """
        self._lifecycle_service = lifecycle_service
        self._dead_letter_service = dead_letter_service
        self._scheduler = scheduler

    def reconcile(self, task_id: str = None, now: Optional[datetime] = None) -> RetryReconciliationResult:
        """Reconcile task_id's own schedule (and, only in this scoped
        mode, whether it is missing one it should have), or every
        currently SCHEDULED record when task_id is omitted.

        Raises:
            InvalidQueueEntryError: If task_id is given and is not a
                non-empty string, or now is given and is not a datetime
        """
        if task_id is not None and (not isinstance(task_id, str) or not task_id.strip()):
            raise InvalidQueueEntryError("task_id must be a non-empty string when given")
        now = self._resolve_now(now)

        if task_id is not None:
            schedule = self._scheduler.get_retry_schedule(task_id)
            schedules = [schedule] if schedule is not None and schedule.status == SCHEDULED else []
        else:
            schedules = [schedule for schedule in self._scheduler.store.list() if schedule.status == SCHEDULED]

        valid, due, stale, invalid = [], [], [], []
        for schedule in schedules:
            bucket = self._classify(schedule, now)
            {"valid": valid, "due": due, "stale": stale, "invalid": invalid}[bucket].append(schedule)

        missing = []
        if task_id is not None and not schedules and self._should_have_schedule(task_id, now):
            missing.append(task_id)

        actions_required = self._build_actions(due, stale, invalid, missing)

        return RetryReconciliationResult(
            task_id=task_id,
            valid_schedules=valid,
            due_schedules=due,
            stale_schedules=stale,
            invalid_schedules=invalid,
            missing_schedules=missing,
            actions_required=actions_required,
        )

    def _classify(self, schedule, now: datetime) -> str:
        task_id = schedule.task_id

        try:
            task = self._lifecycle_service.get(task_id)
        except UnknownAgentTaskError:
            return "invalid"

        if self._dead_letter_service.get(task_id) is not None:
            return "invalid"

        if task.current_state == COMPLETED:
            return "invalid"

        eligibility = self._scheduler.resolve_eligibility(task_id, now=now)
        if not eligibility.eligible:
            return "invalid"

        expected_attempt = (eligibility.attempt_count or 0) + 1
        if schedule.attempt != expected_attempt:
            return "stale"

        return "due" if schedule.eligible_at <= now else "valid"

    def _should_have_schedule(self, task_id: str, now: datetime) -> bool:
        try:
            task = self._lifecycle_service.get(task_id)
        except UnknownAgentTaskError:
            return False

        if task.current_state == COMPLETED:
            return False
        if self._dead_letter_service.get(task_id) is not None:
            return False

        return self._scheduler.resolve_eligibility(task_id, now=now).eligible

    @staticmethod
    def _build_actions(due, stale, invalid, missing) -> list:
        actions = []
        for schedule in due:
            actions.append(f"enqueue retry for task {schedule.task_id!r} (schedule is due)")
        for schedule in stale:
            actions.append(f"cancel and reschedule retry for task {schedule.task_id!r} (attempt is stale)")
        for schedule in invalid:
            actions.append(f"cancel retry schedule for task {schedule.task_id!r} (no longer a valid candidate)")
        for task_id in missing:
            actions.append(f"schedule retry for task {task_id!r} (eligible but has no schedule)")
        return actions

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidQueueEntryError("now must be a datetime when given")
        return now
