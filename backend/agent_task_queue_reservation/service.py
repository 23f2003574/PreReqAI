from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from numbers import Real
from threading import RLock
from typing import Optional, Union

from backend.agent_task_queue import (
    ConflictingClaimError,
    LLMAgentTaskQueueService,
    UnknownQueueEntryError,
)

from .in_memory_store import InMemoryAgentTaskQueueReservationStore
from .models import InvalidReservationError, QueueReservation
from .store import AgentTaskQueueReservationStore

# The default ownership window when reserve() is not given an explicit
# ttl -- a short, worker-lease-sized default (unlike backend.
# agent_policy_risk_approval.DEFAULT_APPROVAL_WINDOW's own 24 hours, or
# backend.agent_policy_risk_escalation.DEFAULT_ESCALATION_WINDOW's own
# 48: those bound a *human* decision window, this bounds one worker's
# uninterrupted hold on one task before it must be considered abandoned
# and made claimable again).
DEFAULT_RESERVATION_TTL = timedelta(minutes=5)


class LLMAgentTaskQueueReservationService:
    """Layers a time-bound ownership window on top of a Commit #1
    backend.agent_task_queue.LLMAgentTaskQueueService's own claim() --
    not a second queue (Rule: "do not duplicate queue entries"): every
    QueueReservation this service saves exists only alongside a live
    Commit #1 QueueEntry whose own claimant_id it keeps in lock-step via
    that service's own claim()/release(), and every exclusivity/missing-
    entry rule this service enforces is exactly Commit #1's own claim()/
    release() rules -- reserve() never decides "is this task_id
    claimable" on its own account, it always asks Commit #1's queue
    service to actually claim it.

    What Commit #1 does not have is expiration: its own claim() holds
    forever until an explicit release()/remove(). This service adds
    exactly that one missing piece -- reserved_at/expires_at bookkeeping
    -- in its own store, alongside (never instead of) Commit #1's own
    claimant_id/claimed_at.

    reserve() is idempotent per the same-still-valid owner (Rule: reuse
    Commit #1's own idempotency conventions): calling it again for a
    task_id already reserved by the same claimant_id, before expiry,
    returns the existing reservation unchanged rather than renewing it
    -- a caller that wants a longer window calls reserve() again only
    after release()ing, or waits for expire_stale_reservations()/lazy
    expiry to reclaim it. A still-valid reservation held by a *different*
    claimant_id raises ConflictingClaimError, reusing Commit #1's own
    exception (Rule: "reuse existing ... error conventions") rather than
    a parallel type for the same "someone else already holds this"
    idea.

    Expiration is handled the same two ways
    backend.agent_policy_risk_approval/backend.agent_policy_risk_escalation
    already split it:
      - Lazily, at read time: get_reservation()/is_reservation_valid()
        (and reserve()'s own existing-reservation check) treat a
        past-expires_at reservation as already gone, without needing
        anyone to have called anything else first. Unlike those two
        modules' own effective_status() (a status-string transition,
        REQUIRED/PENDING -> EXPIRED), QueueReservation carries no status
        field to transition at all -- there is nothing to leave stored
        as "EXPIRED"; a lapsed reservation simply reads as absent
        (Rule: "Expired reservations become claimable again" -- absence
        is exactly what makes a task_id claimable again through
        reserve()), so a direct expires_at/now comparison is the whole
        rule, not a borrowed status machine that would not fit this
        record's own shape.
      - Durably, on demand: expire_stale_reservations() -- modeled
        directly on backend.agent_policy_risk_expiration.
        LLMAgentRiskExpirationService.expire_pending()'s own "explicit,
        caller-invoked sweep; never a background scheduler" discipline
        -- releases the underlying Commit #1 claim and deletes every
        currently past-due reservation in one call, returning how many
        it cleared.

    release() (and expire_stale_reservations()'s own per-item cleanup)
    is safe to call when there is nothing to release, the same
    "safe/idempotent repeated calls, a no-op rather than an error, when
    the target no longer exists" discipline
    backend.agent_task_dependency_readiness_invalidation's own
    invalidate()/invalidate_dependents() already establish for a
    comparable repeated-call scenario -- release() only ever raises for
    a genuine conflict (someone else currently, validly, owns it), never
    merely because there is nothing left to do.

    Reservation state never feeds back into task lifecycle (Rule:
    "Reservation state is separate from task lifecycle"): nothing here
    calls backend.agent_task_lifecycle.LLMAgentTaskLifecycleService.
    transition(), and nothing here executes or retries task_id itself
    (Rule: "No task execution or automatic retry").
    """

    def __init__(
        self,
        queue_service: LLMAgentTaskQueueService,
        store: AgentTaskQueueReservationStore = None,
        default_ttl: timedelta = None,
    ):
        """
        Args:
            queue_service: The exact Commit #1 LLMAgentTaskQueueService
                instance holding the QueueEntry records this service
                reserves ownership windows over -- required, never
                defaulted (a fresh instance's own in-memory store could
                never hold any real queue entry).
            store: Defaults to a fresh
                InMemoryAgentTaskQueueReservationStore.
            default_ttl: The ownership window used when reserve()'s own
                ttl argument is omitted. Defaults to
                DEFAULT_RESERVATION_TTL.
        """
        self._queue_service = queue_service
        self.store = store if store is not None else InMemoryAgentTaskQueueReservationStore()
        self._default_ttl = default_ttl if default_ttl is not None else DEFAULT_RESERVATION_TTL
        self._lock = RLock()

    def reserve(self, task_id: str, claimant_id: str, ttl: Optional[Union[int, float]] = None) -> QueueReservation:
        """Reserve task_id for claimant_id for ttl seconds (or
        default_ttl when ttl is omitted), actually claiming it in
        Commit #1's own queue underneath.

        Raises:
            InvalidReservationError: If task_id/claimant_id is missing
                or blank, or ttl is given and is not a positive number
            UnknownQueueEntryError: If task_id is not currently queued
                (Commit #1's own claim() error, propagated unchanged)
            ConflictingClaimError: If task_id is currently, validly
                reserved by a different claimant_id
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidReservationError("task_id is required and must be a non-empty string")
        if not claimant_id or not isinstance(claimant_id, str):
            raise InvalidReservationError("claimant_id is required and must be a non-empty string")
        if ttl is not None and (not isinstance(ttl, Real) or isinstance(ttl, bool) or ttl <= 0):
            raise InvalidReservationError("ttl must be a positive number of seconds when given")

        window = timedelta(seconds=ttl) if ttl is not None else self._default_ttl

        with self._lock:
            now = datetime.now(timezone.utc)
            existing = self.store.get(task_id)
            if existing is not None:
                if existing.expires_at > now:
                    if existing.claimant_id == claimant_id:
                        return existing
                    raise ConflictingClaimError(
                        f"cannot reserve task {task_id!r}: already reserved by {existing.claimant_id!r}"
                    )
                # Past its own deadline -- release the stale claim
                # underneath before minting a fresh reservation, the
                # same "a lapsed window is never silently resurrected,
                # but a fresh one may now be opened" fall-through
                # backend.agent_policy_risk_approval.LLMAgentRiskApprovalGate.
                # evaluate() already uses for its own stale requirement.
                self._discard(existing)

            entry = self._queue_service.claim(task_id, claimant_id)
            reservation = QueueReservation(
                task_id=entry.task_id, claimant_id=claimant_id, expires_at=now + window, reserved_at=now
            )
            return self.store.save(reservation)

    def release(self, task_id: str, claimant_id: str) -> None:
        """Release claimant_id's reservation of task_id, if any, and
        the underlying Commit #1 claim along with it. A no-op if
        task_id has no reservation, or its own reservation has already
        expired (see this class's own docstring: "safe to call when
        there is nothing to release").

        Raises:
            InvalidReservationError: If claimant_id is missing or blank
            ConflictingClaimError: If task_id is currently, validly
                reserved by a different claimant_id
        """
        if not claimant_id or not isinstance(claimant_id, str):
            raise InvalidReservationError("claimant_id is required and must be a non-empty string")

        with self._lock:
            existing = self.store.get(task_id)
            if existing is None:
                return

            if existing.expires_at <= datetime.now(timezone.utc):
                self._discard(existing)
                return

            if existing.claimant_id != claimant_id:
                raise ConflictingClaimError(
                    f"cannot release task {task_id!r}: reserved by {existing.claimant_id!r}, not {claimant_id!r}"
                )

            self._discard(existing)

    def get_reservation(self, task_id: str) -> Optional[QueueReservation]:
        """task_id's current reservation, or None if it has none, or
        its own reservation has already lapsed (Rule: "Expired
        reservations become claimable again" -- a lapsed one is never
        returned as if it were still current)."""
        reservation = self.store.get(task_id)
        if reservation is None:
            return None
        if reservation.expires_at <= datetime.now(timezone.utc):
            return None
        return reservation

    def is_reservation_valid(self, task_id: str) -> bool:
        """Shorthand for get_reservation(task_id) is not None."""
        return self.get_reservation(task_id) is not None

    def expire_stale_reservations(self) -> int:
        """Durably release and discard every currently past-due
        reservation (across every task_id this store holds), returning
        how many were cleared. An explicit, caller-invoked sweep --
        never triggered on its own (Rule: "no worker/scheduler";
        mirrors backend.agent_policy_risk_expiration.
        LLMAgentRiskExpirationService.expire_pending()'s own "a caller
        decides when to call it" discipline). Safe to call repeatedly:
        once a reservation is cleared, a later call simply no longer
        finds it (Rule: "Repeated ... expiration is safe and
        deterministic")."""
        with self._lock:
            now = datetime.now(timezone.utc)
            stale = [reservation for reservation in self.store.list() if reservation.expires_at <= now]
            for reservation in stale:
                self._discard(reservation)
            return len(stale)

    def _discard(self, reservation: QueueReservation) -> None:
        """Release the underlying Commit #1 claim (tolerating it having
        already been removed/reclaimed out from under this reservation
        -- this service never assumes it is the sole thing mutating
        Commit #1's own queue) and drop this reservation's own record."""
        try:
            self._queue_service.release(reservation.task_id, reservation.claimant_id)
        except (UnknownQueueEntryError, ConflictingClaimError):
            pass
        self.store.delete(reservation.task_id)

    @contextmanager
    def atomic(self):
        """Exposes this service's own RLock, the same way Commit #1's
        own LLMAgentTaskQueueService.atomic() does and for the same
        reason -- Commit #5's own LLMAgentTaskQueueBatchService grouping
        several reserve() calls under one hold. See that method's own
        docstring for what this does and does not guarantee (mutual
        exclusion only, no rollback)."""
        with self._lock:
            yield
