from typing import Optional

from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService
from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService
from backend.agent_task_state_history import LLMAgentTaskStateHistoryService

from .in_memory_store import InMemoryDeadLetterStore
from .models import DeadLetterEntry
from .store import DeadLetterStore


class LLMAgentTaskDeadLetterService:
    """Sets permanently-unprocessable task_ids aside, out of normal
    queue handling, without ever inventing a second lifecycle or retry
    system of its own (Rule): dead_letter()/restore() only ever compose
    Commit #1's own queue_service.remove()/enqueue() and Commit #1's
    own lifecycle_service.get() -- there is no separate "is this task
    dead" flag anywhere else in this series for those methods to have
    grown out of sync with; a dead-lettered task_id is, structurally,
    simply a task_id with no QueueEntry and a DeadLetterEntry instead.

    dead_letter() moves the entry out of normal selection (Rule:
    "Move the queue entry out of normal selection") the same way every
    other commit in this series has always removed a queue entry: by
    calling Commit #1's own queue_service.remove() (a no-op if task_id
    was not actually queued -- see rebalance()'s/expire()'s own
    precedent for tolerating "already gone"). Commit #4's own
    LLMAgentTaskQueueSelectionService needs no changes at all for this:
    it already only ever reads whatever queue_service.store currently
    holds, so a removed entry is already invisible to it.

    Preserves the task itself (Rule: "Preserve the task itself" /
    "Do not silently alter task lifecycle"): nothing here ever calls
    lifecycle_service.transition() -- the underlying Commit #1 AgentTask
    record, and its own current_state, is never touched by either
    dead_letter() or restore().

    metadata captures a reference to failure information this service
    did not itself produce (Rule: "Retain the original failure reason/
    context using existing references") -- task_id's own Commit #1
    AgentTask.current_state/previous_state/transition_reason as of
    dead_letter() time, plus (only when a state_history_service was
    supplied) its own most recent backend.agent_task_state_history.
    TaskTransitionRecord, verbatim. See DeadLetterEntry's own docstring
    for why this is kept separate from dead_letter()'s own caller-
    supplied reason.

    restore() is exactly Commit #1's own queue_service.enqueue(task_id)
    -- readiness-gated by that same call, not a second readiness check
    of this service's own (Rule: "Restoration must return the task to
    normal queue handling only when existing readiness semantics
    allow it"; "Reuse existing queue removal/selection and readiness
    services"): a task_id that is not currently ready raises exactly
    the TaskNotReadyError enqueue() itself already raises, propagated
    unchanged, and the DeadLetterEntry is left in place (restore did
    not happen) -- only a successful enqueue() removes it.

    Both operations are idempotent (Rule: "Restore is explicit and
    idempotent"; "Duplicate dead-letter/restore operations are safe"):
    dead_letter() on an already-dead-lettered task_id returns the
    existing entry unchanged, ignoring the new reason -- the same
    "idempotency checked before anything else, existing record wins"
    convention Commit #1's own enqueue() already established; restore()
    on a task_id that is not currently dead-lettered is a safe no-op,
    the same "safe when there is nothing there" discipline Commit #2's
    own release() and Commit #7's own expire() already establish.
    """

    def __init__(
        self,
        queue_service: LLMAgentTaskQueueService,
        lifecycle_service: LLMAgentTaskLifecycleService,
        store: DeadLetterStore = None,
        state_history_service: LLMAgentTaskStateHistoryService = None,
    ):
        """
        Args:
            queue_service: The exact Commit #1 LLMAgentTaskQueueService
                instance dead-lettered task_ids are removed from/
                restored to -- required, never defaulted.
            lifecycle_service: The exact Commit #1
                LLMAgentTaskLifecycleService instance holding task_id's
                own AgentTask record -- required, so metadata reflects
                the real task, not an empty fresh store.
            store: Defaults to a fresh InMemoryDeadLetterStore.
            state_history_service: Optional
                backend.agent_task_state_history.LLMAgentTaskStateHistoryService
                -- when given, dead_letter() additionally captures
                task_id's own most recent TaskTransitionRecord into
                metadata. Omit when no such history is being kept for
                queue_service's own tasks.
        """
        self._queue_service = queue_service
        self._lifecycle_service = lifecycle_service
        self.store = store if store is not None else InMemoryDeadLetterStore()
        self._state_history_service = state_history_service

    def dead_letter(self, task_id: str, reason: str) -> DeadLetterEntry:
        """Set task_id aside, out of normal queue handling, recording
        reason and a snapshot of its own existing failure/lifecycle
        information. Idempotent: if task_id is already dead-lettered,
        returns that existing entry unchanged.

        Raises:
            InvalidQueueEntryError: If task_id or reason is missing or
                blank
            UnknownAgentTaskError: If task_id was never created
                (Commit #1's own lifecycle_service.get() error,
                propagated unchanged)
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidQueueEntryError("task_id is required and must be a non-empty string")
        if not reason or not isinstance(reason, str):
            raise InvalidQueueEntryError("reason is required and must be a non-empty string")

        existing = self.store.get(task_id)
        if existing is not None:
            return existing

        task = self._lifecycle_service.get(task_id)

        with self._queue_service.atomic():
            if self._queue_service.contains(task_id):
                self._queue_service.remove(task_id)

        metadata = {
            "lifecycle_state": task.current_state,
            "previous_state": task.previous_state,
            "transition_reason": task.transition_reason,
        }
        if self._state_history_service is not None:
            latest = self._state_history_service.get_latest(task_id)
            if latest is not None:
                metadata["latest_transition"] = latest.to_dict()

        entry = DeadLetterEntry(task_id=task_id, reason=reason, metadata=metadata)
        return self.store.save(entry)

    def get(self, task_id: str) -> Optional[DeadLetterEntry]:
        """task_id's current DeadLetterEntry, or None if it is not
        currently dead-lettered."""
        return self.store.get(task_id)

    def list(self, limit: int = None) -> list:
        """Every currently dead-lettered entry, oldest first, optionally
        capped to the first limit entries.

        Raises:
            InvalidQueueEntryError: If limit is given and is not a
                non-negative int
        """
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise InvalidQueueEntryError("limit must be a non-negative int when given")

        entries = sorted(self.store.list(), key=lambda entry: (entry.failed_at, entry.task_id))
        return entries if limit is None else entries[:limit]

    def restore(self, task_id: str) -> None:
        """Return task_id to normal queue handling, only when it is
        currently ready (Commit #1's own enqueue() gate). A no-op if
        task_id is not currently dead-lettered.

        Raises:
            InvalidQueueEntryError: If task_id is missing or blank
            TaskNotReadyError: If task_id does not currently satisfy
                readiness (Commit #1's own enqueue() error, propagated
                unchanged) -- the DeadLetterEntry is left in place
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidQueueEntryError("task_id is required and must be a non-empty string")

        entry = self.store.get(task_id)
        if entry is None:
            return

        self._queue_service.enqueue(task_id)
        self.store.delete(task_id)
