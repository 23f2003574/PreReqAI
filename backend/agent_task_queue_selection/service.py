from typing import Optional

from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService, QueueEntry
from backend.agent_task_queue_ordering import LLMAgentTaskQueueOrderingService
from backend.agent_task_queue_reservation import LLMAgentTaskQueueReservationService
from backend.agent_task_readiness import LLMAgentTaskReadinessService


class LLMAgentTaskQueueSelectionService:
    """Chooses which queued task_id(s) should be worked on next -- a
    read-only composition of Commits #1-#3, never a fourth queue,
    readiness gate, or ordering rule of its own (Rule: "do not duplicate
    ordering/readiness logic"; "do not invent workers or scheduling
    infrastructure"). select_next()/select() only ever read; nothing
    here claims, reserves, removes, or executes anything (Rule:
    "Selection is read-only" / "Do not claim/reserve or execute
    selected tasks").

    The five selection steps this Goal lists map directly onto this
    repository's own existing services, one per step, never
    reimplemented:
      1. "Read queued tasks" -- Commit #1's own
         LLMAgentTaskQueueService.store.list() (the same public .store
         other cross-service compositions in this repository already
         read directly, e.g. backend.agent_policy_risk_review_queue.
         LLMAgentRiskReviewQueue._active_escalation_id() reading
         escalation_service.store).
      2. "Exclude tasks that are no longer ready" -- Commit #1's own
         readiness_service.is_ready(task_id), the exact gate enqueue()
         itself already uses (Rule: "Never bypass task readiness"): a
         task_id that was ready at enqueue() time but is not any more
         (Commit #1 never auto-evicts on a readiness change) is
         excluded here, not merely ranked last.
      3. "Exclude tasks with active reservations" -- Commit #2's own
         reservation_service.is_reservation_valid(task_id) (Rule: "Use
         Commit #2 reservation semantics"). A raw Commit #1 claim made
         by calling queue_service.claim() directly, bypassing Commit
         #2's reserve(), carries no matching reservation and is
         deliberately out of this check's scope -- Commit #2's own
         design keeps QueueEntry.claimant_id and QueueReservation.
         claimant_id in lock-step for every claim made *through* it,
         and this service's only contract is with that reservation
         layer, exactly as the Goal itself frames step 3 in terms of
         reservations, not raw claims.
      4. "Apply the existing queue ordering" -- Commit #3's own
         ordering_service.order(candidates), run only after steps 2-3
         have already filtered candidates down to ones that qualify at
         all (ordering never decides *whether* an entry is selectable,
         only what order the selectable ones come in).
      5. "Return up to limit candidates" -- a plain list slice; no
         further computation.

    Deterministic for identical repository state (Rule): every step
    above is itself a pure read of already-persisted state
    (store.list()/is_ready()/is_reservation_valid()/order() are all
    read-only and side-effect free -- see each of those methods' own
    docstrings), so calling select_next()/select() twice in a row
    without anything else changing in between always returns the same
    result.

    Stale/missing entries are handled explicitly, never by raising for
    an ordinary "nothing here": select(task_id) returns None for a
    task_id that is not currently queued at all, exactly as
    is_ready(task_id) already returns False (rather than raising) for a
    task_id that was never created -- both read as "not currently
    selectable," the same tolerant-per-item discipline backend.
    agent_task_readiness_projection.LLMAgentTaskReadinessProjectionService.
    list_affected() already uses for an unresolvable task_id.
    """

    def __init__(
        self,
        queue_service: LLMAgentTaskQueueService,
        readiness_service: LLMAgentTaskReadinessService,
        reservation_service: LLMAgentTaskQueueReservationService,
        ordering_service: LLMAgentTaskQueueOrderingService = None,
    ):
        """
        Args:
            queue_service: The exact Commit #1 LLMAgentTaskQueueService
                instance holding the entries selected from -- required,
                never defaulted.
            readiness_service: The exact Commit #1
                LLMAgentTaskReadinessService instance queue_service
                itself gates enqueue() through -- required, so
                "currently ready" always means the same thing here as
                it does at enqueue() time.
            reservation_service: The exact Commit #2
                LLMAgentTaskQueueReservationService instance built over
                queue_service -- required, so "actively reserved" is
                read from the one real reservation store, not a second
                one.
            ordering_service: Defaults to a fresh
                LLMAgentTaskQueueOrderingService with no readiness_service
                of its own -- deliberately, since by the time ordering
                runs (step 4), every remaining candidate has already
                passed step 2's own readiness filter, so ranking by
                readiness again would be a constant, redundant re-check
                of the exact same thing for every candidate. Pass a
                different ordering_service to change tie-breaking, or
                to add other criteria of its own.
        """
        self._queue_service = queue_service
        self._readiness_service = readiness_service
        self._reservation_service = reservation_service
        self._ordering_service = (
            ordering_service if ordering_service is not None else LLMAgentTaskQueueOrderingService()
        )

    def select_next(self, limit: int = 1) -> list:
        """Up to limit currently-selectable entries, in Commit #3's own
        ordering. Never claims, reserves, or removes anything (Rule:
        "Selection does not mutate queue/reservation state").

        Raises:
            InvalidQueueEntryError: If limit is not a non-negative int
        """
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
            raise InvalidQueueEntryError("limit must be a non-negative int")

        candidates = [entry for entry in self._queue_service.store.list() if self._is_selectable(entry)]
        return self._ordering_service.order(candidates)[:limit]

    def select(self, task_id: str) -> Optional[QueueEntry]:
        """task_id's own queue entry, if it is currently queued and
        currently selectable (ready, and not actively reserved) --
        otherwise None, whether because task_id was never queued, its
        entry is no longer ready, or it is actively reserved by
        someone.

        Raises:
            InvalidQueueEntryError: If task_id is missing or blank
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidQueueEntryError("task_id is required and must be a non-empty string")

        entry = self._queue_service.store.get(task_id)
        if entry is None or not self._is_selectable(entry):
            return None
        return entry

    def _is_selectable(self, entry: QueueEntry) -> bool:
        if not self._readiness_service.is_ready(entry.task_id):
            return False
        if self._reservation_service.is_reservation_valid(entry.task_id):
            return False
        return True
