from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_queue import InvalidQueueEntryError
from backend.agent_task_queue_retry_eligibility import (
    LLMAgentTaskQueueRetryEligibilityService,
    RetryEligibilityResult,
)

from .in_memory_store import InMemoryRetryScheduleStore
from .models import CANCELLED, SCHEDULED, TaskRetrySchedule
from .store import RetryScheduleStore


class IneligibleForRetryError(ValueError):
    """Raised when schedule_retry() is given a task_id that Commit #9's
    own LLMAgentTaskQueueRetryEligibilityService currently reports as
    not eligible (Rule: "Ineligible tasks cannot receive a retry
    schedule") -- this covers every one of Commit #9's own reasons
    uniformly (dead-lettered, non-retryable, retry limit reached,
    backoff not elapsed, not ready): this class never re-derives or
    duplicates any of those checks, it only refuses to schedule when
    Commit #9 already said no."""


class LLMAgentTaskRetryScheduler:
    """Calculates *when* an eligible task_id may next re-enter the
    queue, and persists that as data -- never a worker, timer, or
    scheduler that fires anything itself (Rule: "Do not invent a
    worker or scheduler"; "Scheduling only; never execute or enqueue a
    retry"): schedule_retry() never calls backend.agent_task_queue.
    LLMAgentTaskQueueService.enqueue(), and get_due_retries() never
    does either (Rule: "Expose due retries without enqueueing them") --
    a caller decides what, if anything, to do with a due schedule.

    Every rule this class enforces is delegated, never reimplemented:
      - eligibility (Rule 1: "Check existing retry eligibility"; "Respect
        dead-letter state and policy limits"): Commit #9's own
        LLMAgentTaskQueueRetryEligibilityService.check() -- its own
        ineligible verdict (dead-lettered, non-retryable, retry limit
        reached, not ready, ...) is never overridden or second-guessed
        here, only turned into IneligibleForRetryError when
        schedule_retry() is asked to schedule one anyway.
      - backoff timing (Rule 2: "Calculate the next eligible time using
        existing backoff semantics"): Commit #9's own
        RetryEligibilityResult.next_eligible_at, read verbatim -- this
        class has no backoff formula of its own (Rule: "Reuse existing
        retry policy/attempt models"). When Commit #9 reports no backoff
        constraint at all (next_eligible_at is None -- already eligible
        right now), eligible_at is simply now.

    One real tension between the two commits, resolved here rather than
    by changing Commit #9: that service's own check() conflates "may
    retry right now" with "may retry at all" -- a task still inside its
    own backoff window reads as flatly ineligible (Rule there: "Backoff
    window not elapsed -> ineligible"), which is exactly correct for
    "is it OK to enqueue this instant" but would make schedule_retry()
    unable to schedule *anything* for later, defeating this commit's
    own purpose. resolve_eligibility() (below) is where this is
    resolved, without touching Commit #9's own logic or duplicating it:
    it calls check() once at now; if that already reports eligible,
    backoff was never the issue. If not, it reads that same call's own
    next_eligible_at and calls check() a *second* time, at exactly that
    future moment -- every other condition Commit #9 evaluates (dead-
    letter, classification, attempt limit, readiness) does not depend
    on `now` at all, so this second call is eligible if and only if
    backoff timing was the *only* thing blocking the first one.
    schedule_retry() then proceeds only if that resolved result is
    eligible (for the eligible_at the first call already computed);
    otherwise it raises IneligibleForRetryError, exactly as Commit #9
    reported it. resolve_eligibility() is exposed publicly (not
    inlined into schedule_retry() alone) so Commit #11's own
    reconciliation service can reuse this exact same resolution instead
    of a second copy of it (Rule there: "Reuse existing retry
    scheduling and eligibility semantics").

    schedule_retry() is idempotent per attempt (Rule 4: "Prevent
    duplicate schedules for the same retry attempt"): a second call for
    a task_id that already has a live SCHEDULED schedule for the exact
    same attempt number returns that schedule unchanged, the same
    "idempotency checked before creating anything new" convention every
    enqueue()/reserve()/dead_letter() in this series already
    establishes. A schedule for a *different* attempt (task_id failed
    again since the last schedule) or a CANCELLED one replaces it --
    exactly one live schedule exists per task_id at a time, never a
    history of past ones (see TaskRetrySchedule's own docstring).

    cancel_retry() is idempotent (Rule: "Cancellation is idempotent"):
    a no-op, never an error, whether task_id has no schedule at all or
    is already CANCELLED -- the same "safe when there is nothing (left)
    to do" discipline Commit #2's own release() and Commit #7's own
    expire() already establish.

    get_due_retries() is a pure, read-only query -- SCHEDULED records
    whose own eligible_at has passed as of now, sorted deterministically
    (eligible_at, then task_id) -- never a persisted "DUE" status of its
    own (see TaskRetrySchedule's own docstring for why).
    """

    def __init__(
        self,
        eligibility_service: LLMAgentTaskQueueRetryEligibilityService,
        store: RetryScheduleStore = None,
    ):
        """
        Args:
            eligibility_service: The exact Commit #9
                LLMAgentTaskQueueRetryEligibilityService instance wired
                to the same lifecycle/readiness/dead-letter state
                task_id lives in -- required, never defaulted.
            store: Defaults to a fresh InMemoryRetryScheduleStore.
        """
        self._eligibility_service = eligibility_service
        self.store = store if store is not None else InMemoryRetryScheduleStore()

    def resolve_eligibility(self, task_id: str, now: Optional[datetime] = None) -> RetryEligibilityResult:
        """Commit #9's own eligibility verdict for task_id, resolved so
        that a task blocked *only* by its own backoff window not having
        elapsed yet reads as eligible (as of the eligible_at it itself
        reports) rather than flatly ineligible -- see this class's own
        docstring for why. Read-only: never persists anything, and
        never raises for an ineligible task_id (unlike schedule_retry())
        -- it only ever reports.

        Raises:
            InvalidQueueEntryError: If task_id is missing or blank, or
                now is given and is not a datetime
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidQueueEntryError("task_id is required and must be a non-empty string")
        now = self._resolve_now(now)

        eligibility = self._eligibility_service.check(task_id, now=now)
        if eligibility.eligible:
            return eligibility

        eligible_at = eligibility.next_eligible_at if eligibility.next_eligible_at is not None else now
        return self._eligibility_service.check(task_id, now=eligible_at)

    def schedule_retry(self, task_id: str, now: Optional[datetime] = None) -> TaskRetrySchedule:
        """Schedule task_id's next retry attempt, per Commit #9's own
        current eligibility verdict (resolved through
        resolve_eligibility() above).

        Raises:
            InvalidQueueEntryError: If task_id is missing or blank, or
                now is given and is not a datetime
            IneligibleForRetryError: If task_id is not currently
                eligible for retry (Commit #9's own check())
        """
        now = self._resolve_now(now)
        eligibility = self.resolve_eligibility(task_id, now=now)
        eligible_at = eligibility.next_eligible_at if eligibility.next_eligible_at is not None else now

        if not eligibility.eligible:
            raise IneligibleForRetryError(
                f"task {task_id!r} is not eligible for retry: {eligibility.reason}"
            )

        attempt = (eligibility.attempt_count or 0) + 1

        existing = self.store.get(task_id)
        if existing is not None and existing.status == SCHEDULED and existing.attempt == attempt:
            return existing

        schedule = TaskRetrySchedule(
            task_id=task_id,
            attempt=attempt,
            scheduled_at=now,
            eligible_at=eligible_at,
            status=SCHEDULED,
            reason=eligibility.reason,
        )
        return self.store.save(schedule)

    def cancel_retry(self, task_id: str) -> None:
        """Withdraw task_id's current retry schedule, if any.

        Raises:
            InvalidQueueEntryError: If task_id is missing or blank
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidQueueEntryError("task_id is required and must be a non-empty string")

        existing = self.store.get(task_id)
        if existing is None or existing.status == CANCELLED:
            return

        self.store.save(replace(existing, status=CANCELLED))

    def get_retry_schedule(self, task_id: str) -> Optional[TaskRetrySchedule]:
        """task_id's current schedule, exactly as stored (SCHEDULED or
        CANCELLED), or None if it was never scheduled at all.

        Raises:
            InvalidQueueEntryError: If task_id is missing or blank
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidQueueEntryError("task_id is required and must be a non-empty string")
        return self.store.get(task_id)

    def get_due_retries(self, now: Optional[datetime] = None) -> list:
        """Every currently SCHEDULED schedule whose own eligible_at has
        passed as of now, in deterministic order. Never enqueues
        anything (Rule: "Expose due retries without enqueueing them").

        Raises:
            InvalidQueueEntryError: If now is given and is not a
                datetime
        """
        now = self._resolve_now(now)
        due = [
            schedule
            for schedule in self.store.list()
            if schedule.status == SCHEDULED and schedule.eligible_at <= now
        ]
        return sorted(due, key=lambda schedule: (schedule.eligible_at, schedule.task_id))

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidQueueEntryError("now must be a datetime when given")
        return now
