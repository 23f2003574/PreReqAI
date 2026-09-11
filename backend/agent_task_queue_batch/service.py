from backend.agent_task_queue import (
    ConflictingClaimError,
    InvalidQueueEntryError,
    LLMAgentTaskQueueService,
    TaskNotReadyError,
    UnknownQueueEntryError,
)
from backend.agent_task_queue_reservation import InvalidReservationError, LLMAgentTaskQueueReservationService


class BatchOperationError(Exception):
    """Raised by enqueue_many()/claim_many()/remove_many() when at
    least one task_id in the batch failed -- never raised for a fully
    successful batch, and never swallows a failure silently either
    (Rule: "Never silently skip invalid tasks"): every task_id that
    failed is present in failures, with exactly the error the
    equivalent single-item call would have raised for it (Rule: "Batch
    operations must preserve the same correctness guarantees as
    individual operations").

    This repository's own persistence layer (backend.storage.
    AtomicJsonFile atomically replaces one whole file per write(), and
    the in-memory stores are plain dicts -- neither offers a multi-key
    rollback transaction) has nothing to roll back to, so a batch is
    never all-or-nothing: succeeded is exactly which task_ids (or
    entries) *did* commit before this error was raised, and every other
    already-attempted task_id is accounted for, one way or the other,
    in failures. This is what Rule's own "use repository transactions
    ... where available; otherwise follow existing partial-operation
    conventions" means concretely here -- see
    LLMAgentTaskQueueService.atomic()/LLMAgentTaskQueueReservationService.
    atomic() for the one piece of real atomicity this repository's own
    concurrency primitive (threading.RLock) *does* give: mutual
    exclusion against other threads for the whole batch, even though
    there is still no rollback.

    Attributes:
        succeeded: Every task_id that succeeded, in the shape the
            underlying single-item call itself returns (a QueueEntry
            for enqueue_many()/claim_many(), a bare task_id string for
            remove_many()) -- in the order attempted.
        failures: Every (task_id, error) pair that failed, in the order
            attempted. A task_id can appear more than once here (see
            Rule: "Duplicate IDs" -- e.g. remove_many() given the same
            task_id twice fails the second occurrence with
            UnknownQueueEntryError, once the first has already removed
            it), so this is a list of pairs, never a dict keyed by
            task_id.
    """

    def __init__(self, message: str, succeeded: list, failures: list):
        super().__init__(message)
        self.succeeded = succeeded
        self.failures = failures


class LLMAgentTaskQueueBatchService:
    """Batch enqueue/claim/remove over Commits #1-#2 -- never a second
    queue or reservation system (Rule: "do not invent a new transaction
    or storage framework"; "Do not duplicate single-task queue logic"):
    every one of enqueue_many()/claim_many()/remove_many() is nothing
    but a loop calling the exact same single-item
    LLMAgentTaskQueueService.enqueue()/
    LLMAgentTaskQueueReservationService.reserve()/
    LLMAgentTaskQueueService.remove() Commits #1-#2 already validate,
    readiness-check, and persist through. This class adds no readiness,
    reservation, or ordering rule of its own.

    claim_many() calls Commit #2's own reserve() (Rule: "Respect active
    reservations during claims"), not Commit #1's own raw claim() --
    reserve() is what actually understands whether an existing hold on
    a task_id has expired and may be taken over; a raw claim() has no
    notion of that at all (see Commit #2's own docstring).

    Every task_id in a batch is always attempted, never stopped at the
    first failure (the same "run every check, collect every result,
    never fail fast" discipline
    backend.agent_task_readiness.LLMAgentTaskReadinessService.check()
    already established for a comparable multi-item report elsewhere in
    this series) -- see BatchOperationError's own docstring for how
    failures are then reported. A fully successful batch returns
    exactly what its own signature says (list[QueueEntry] for
    enqueue_many()/claim_many(), an int count for remove_many()); a
    batch with any failures raises BatchOperationError instead, never a
    bare partial list with failures silently missing from it.

    Preserves existing queue ordering semantics (Rule) simply by never
    touching a store directly -- every item still goes through Commit
    #1's/#2's own real methods, so Commit #3's own ordering (peek(), or
    a caller's own LLMAgentTaskQueueOrderingService) reads a batch's
    resulting entries exactly the same as it would any individually
    enqueued ones.
    """

    def __init__(
        self,
        queue_service: LLMAgentTaskQueueService,
        reservation_service: LLMAgentTaskQueueReservationService,
    ):
        """
        Args:
            queue_service: The exact Commit #1 LLMAgentTaskQueueService
                instance batch enqueue_many()/remove_many() operate
                against -- required, never defaulted.
            reservation_service: The exact Commit #2
                LLMAgentTaskQueueReservationService instance built over
                queue_service -- required, so claim_many() respects the
                one real reservation store, not a second one.
        """
        self._queue_service = queue_service
        self._reservation_service = reservation_service

    def enqueue_many(self, task_ids: list, priority: int = None) -> list:
        """Enqueue every task_id in task_ids (Commit #1's own
        enqueue() semantics, including its own idempotency for a
        task_id already queued or repeated within this same batch).

        Raises:
            InvalidQueueEntryError: If task_ids is not a list
            BatchOperationError: If any task_id could not be enqueued
                (see BatchOperationError's own docstring)
        """
        self._validate_task_ids(task_ids)

        succeeded = []
        failures = []
        with self._queue_service.atomic():
            for task_id in task_ids:
                try:
                    succeeded.append(self._queue_service.enqueue(task_id, priority))
                except (InvalidQueueEntryError, TaskNotReadyError) as error:
                    failures.append((task_id, error))

        if failures:
            raise BatchOperationError(
                f"{len(failures)} of {len(task_ids)} task(s) could not be enqueued", succeeded, failures
            )
        return succeeded

    def claim_many(self, task_ids: list, claimant_id: str) -> list:
        """Reserve every task_id in task_ids for claimant_id (Commit
        #2's own reserve() semantics, including its own idempotency for
        an already-valid reservation held by the same claimant_id).

        Raises:
            InvalidQueueEntryError: If task_ids is not a list
            BatchOperationError: If any task_id could not be reserved
                (see BatchOperationError's own docstring) -- including a
                task_id currently reserved by someone else
                (ConflictingClaimError) or not currently queued at all
                (UnknownQueueEntryError)
        """
        self._validate_task_ids(task_ids)

        succeeded = []
        failures = []
        with self._reservation_service.atomic():
            for task_id in task_ids:
                try:
                    succeeded.append(self._reservation_service.reserve(task_id, claimant_id))
                except (InvalidReservationError, UnknownQueueEntryError, ConflictingClaimError) as error:
                    failures.append((task_id, error))

        if failures:
            raise BatchOperationError(
                f"{len(failures)} of {len(task_ids)} task(s) could not be claimed", succeeded, failures
            )
        return succeeded

    def remove_many(self, task_ids: list) -> int:
        """Remove every task_id in task_ids from the queue (Commit #1's
        own remove() semantics) and return how many were actually
        removed.

        Raises:
            InvalidQueueEntryError: If task_ids is not a list
            BatchOperationError: If any task_id could not be removed
                (see BatchOperationError's own docstring) -- including a
                task_id that was never queued, or already removed
                earlier in this same batch (Rule: "Duplicate IDs")
        """
        self._validate_task_ids(task_ids)

        succeeded = []
        failures = []
        with self._queue_service.atomic():
            for task_id in task_ids:
                try:
                    self._queue_service.remove(task_id)
                    succeeded.append(task_id)
                except (InvalidQueueEntryError, UnknownQueueEntryError) as error:
                    failures.append((task_id, error))

        if failures:
            raise BatchOperationError(
                f"{len(failures)} of {len(task_ids)} task(s) could not be removed", succeeded, failures
            )
        return len(succeeded)

    @staticmethod
    def _validate_task_ids(task_ids) -> None:
        if not isinstance(task_ids, list):
            raise InvalidQueueEntryError("task_ids must be a list")
