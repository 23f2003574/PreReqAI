from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService, UnknownQueueEntryError
from backend.agent_task_queue_reservation import LLMAgentTaskQueueReservationService

from .models import QueueExpirationResult

# How long a task may sit queued at all before its own QueueEntry is
# considered abandoned -- a queue-wide policy, not a per-entry field:
# Commit #1's own QueueEntry carries no expires_at of its own (unlike
# Commit #2's own QueueReservation, whose expires_at is a genuine
# per-reservation lease), so this is configured here, at the service
# level, the same way Commit #2's own DEFAULT_RESERVATION_TTL is a
# service-level default rather than something stored on each record.
# Longer than Commit #2's own 5-minute worker-lease default (a task may
# legitimately sit *unclaimed* in the queue for a while before any
# worker ever picks it up at all -- that is not abandonment, only an
# actual claim going stale is), shorter than backend.
# agent_policy_risk_approval.DEFAULT_APPROVAL_WINDOW's own 24 hours (a
# human decision window, not a machine queue's own dwell time).
DEFAULT_QUEUE_ENTRY_TTL = timedelta(hours=1)


class LLMAgentTaskQueueExpirationService:
    """Prunes QueueEntry records that have sat queued longer than this
    repository's own configured queue lifetime -- never a second queue,
    reservation store, or scheduler of its own (Rule: "do not invent a
    new scheduler or background-worker system"). Reuses Commit #1's own
    QueueEntry.queued_at (Rule: "reuse existing TTL/expiration
    utilities and persistence") rather than adding a new timestamp
    field, and Commit #2's own reservation machinery verbatim for
    everything reservation-related (Rule: "Handle expired reservations
    using Commit #2 semantics"; "Do not duplicate ... reservation
    logic" -- carried over from Commit #6's own equivalent rule).

    "Queue lifetime" here means exactly what Commit #2's own
    expires_at/effective_status comparisons already mean for a
    reservation, applied to QueueEntry.queued_at instead of a
    reservation's own expires_at: an entry is expired once
    queued_at + max_queue_age <= now (see this class's own _is_expired()
    -- the same "<=" convention backend.agent_policy_risk_approval.
    effective_status() already uses).

    An expired entry that is still actively, validly reserved (Commit
    #2's own is_reservation_valid()) is never removed (Rule: "Preserve
    valid active reservations/entries") -- it is reported as expired
    (its own queue lifetime genuinely lapsed) but skipped, the same
    "protect a reserved entry from removal regardless of the other
    reason it would otherwise be pruned" precedent Commit #6's own
    rebalancer already established for readiness-driven removal. This
    class never removes the underlying task itself (Rule: "Do not
    silently delete tasks themselves"): only the QueueEntry -- Commit
    #1's own AgentTask lifecycle record is never touched, and neither
    is anything about task_id's own lifecycle state (Rule: "Do not
    change task lifecycle unless the existing architecture explicitly
    requires it" -- nothing here does).

    expire_all() additionally runs Commit #2's own
    reservation_service.expire_stale_reservations() first, as a bulk
    maintenance pass over the *whole* reservation store, before
    evaluating queue-entry age -- so a task_id whose reservation alone
    has gone stale (the claimant abandoned it, but the entry itself is
    still well within its own queue lifetime) has that claim released
    and becomes reclaimable again, exactly Commit #2's own behavior,
    simply invoked rather than reimplemented. expire() (single-task)
    deliberately does not trigger that same bulk sweep -- it would mean
    a call scoped to one task_id silently mutating unrelated task_ids'
    reservations. A single expire() call still decides correctly
    whether *its own* task_id is protected, since Commit #2's own
    is_reservation_valid() is already lazily accurate (expired reads as
    invalid) without needing the bulk sweep first; it just does not
    also durably clean up a stale reservation *row* for an unrelated
    task_id along the way.

    Deterministic for a supplied now (Rule): every comparison here uses
    exactly the now passed to (or defaulted once, at the top of) the
    call, never a fresh datetime.now() read partway through. Repeated
    calls with the same, or a later, now are safe/idempotent (Rule): an
    already-removed entry is simply no longer found by a later call
    (nothing left to act on), and an already-skipped (still validly
    reserved) entry is re-evaluated fresh each time, exactly as
    accurately as the first time.
    """

    def __init__(
        self,
        queue_service: LLMAgentTaskQueueService,
        reservation_service: LLMAgentTaskQueueReservationService,
        max_queue_age: timedelta = None,
    ):
        """
        Args:
            queue_service: The exact Commit #1 LLMAgentTaskQueueService
                instance expired -- required, never defaulted.
            reservation_service: The exact Commit #2
                LLMAgentTaskQueueReservationService instance built over
                queue_service -- required, so "actively reserved" is
                read from (and, for expire_all(), swept through) the
                one real reservation store.
            max_queue_age: Defaults to DEFAULT_QUEUE_ENTRY_TTL.
        """
        self._queue_service = queue_service
        self._reservation_service = reservation_service
        self._max_queue_age = max_queue_age if max_queue_age is not None else DEFAULT_QUEUE_ENTRY_TTL

    def find_expired(self, now: Optional[datetime] = None) -> list:
        """Every currently queued entry whose own queue lifetime has
        lapsed as of now -- a pure, read-only query (Behavior 1-2):
        never removes anything, never consults reservations at all
        (whether an expired entry is actually removable is expire()/
        expire_all()'s own decision, not a detection concern)."""
        now = self._resolve_now(now)
        return [entry for entry in self._queue_service.store.list() if self._is_expired(entry, now)]

    def expire(self, task_id: str, now: Optional[datetime] = None) -> QueueExpirationResult:
        """Expire task_id alone, if it is currently queued and past its
        own queue lifetime.

        Raises:
            InvalidQueueEntryError: If task_id is missing or blank, or
                now is given and is not a datetime
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidQueueEntryError("task_id is required and must be a non-empty string")
        now = self._resolve_now(now)

        with self._queue_service.atomic():
            entry = self._queue_service.store.get(task_id)
            if entry is None:
                return QueueExpirationResult(errors=[(task_id, UnknownQueueEntryError(task_id))])

            if not self._is_expired(entry, now):
                return QueueExpirationResult()

            if self._reservation_service.is_reservation_valid(task_id):
                return QueueExpirationResult(expired_tasks=[task_id], skipped_tasks=[task_id])

            self._queue_service.remove(task_id)
            return QueueExpirationResult(expired_tasks=[task_id], removed_entries=[entry])

    def expire_all(self, now: Optional[datetime] = None) -> QueueExpirationResult:
        """Expire every currently queued entry past its own queue
        lifetime, across the whole queue.

        Raises:
            InvalidQueueEntryError: If now is given and is not a
                datetime
        """
        now = self._resolve_now(now)

        with self._queue_service.atomic():
            self._reservation_service.expire_stale_reservations()

            expired_tasks, removed_entries, skipped_tasks = [], [], []
            for entry in self.find_expired(now):
                expired_tasks.append(entry.task_id)
                if self._reservation_service.is_reservation_valid(entry.task_id):
                    skipped_tasks.append(entry.task_id)
                    continue
                self._queue_service.remove(entry.task_id)
                removed_entries.append(entry)

        return QueueExpirationResult(
            expired_tasks=expired_tasks, removed_entries=removed_entries, skipped_tasks=skipped_tasks
        )

    def _is_expired(self, entry, now: datetime) -> bool:
        return entry.queued_at + self._max_queue_age <= now

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidQueueEntryError("now must be a datetime when given")
        return now
