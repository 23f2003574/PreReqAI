from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService
from backend.agent_task_queue_ordering import LLMAgentTaskQueueOrderingService
from backend.agent_task_queue_reservation import LLMAgentTaskQueueReservationService
from backend.agent_task_readiness import LLMAgentTaskReadinessService

from .models import QueueRebalanceResult


class LLMAgentTaskQueueRebalancer:
    """Prunes ineligible queue entries and reports how the remaining
    ones' relative order has drifted since this instance last looked --
    never a second queue, readiness gate, or ordering rule of its own
    (Rule: "do not create another queue or scheduler"; "Do not
    duplicate readiness or ordering logic"). Every decision rebalance()
    makes is delegated straight to an existing service:
      - eligibility: Commit #1's own readiness_service.is_ready()
      - protection: Commit #2's own
        reservation_service.is_reservation_valid()
      - order: Commit #3's own ordering_service.order()
      - removal/persistence: Commit #1's own queue_service.remove(),
        under Commit #5's own queue_service.atomic() (Rule: "Persist
        only necessary queue changes" -- removal is the only thing
        this class ever writes; there is nothing else to persist, since
        Commit #1's QueueEntry has no mutable "rank"/"order" field of
        its own to begin with -- order has always been a value Commit
        #3 computes fresh on every read, never stored)

    Why detecting "reordered" needs memory of its own: every QueueEntry
    field (priority, queued_at, task_id) is immutable once enqueued
    (Commit #1's own model), and this class never mutates entries or
    task lifecycle -- so nothing about a still-queued task_id's own
    sort key can ever change *during* one rebalance() call. The only
    thing that can move a task_id's rank between two calls is its own
    readiness flipping between them (e.g. a dependency it was blocked
    on completes, or a policy rule blocking it is lifted) while it
    stayed queued the whole time -- which itself only happens if
    something (Commit #2's own reservation) protected it from being
    *removed* during the window it was not ready. Comparing a fresh
    computation only to itself, within one call, can therefore never
    show any drift at all; genuine "reordered" detection requires
    comparing against what this same instance last recorded. This
    instance keeps that as a small private dict (task_id -> last-known
    rank), not a second durable store: losing it (e.g. on restart)
    only means the next rebalance() treats every survivor as newly
    observed (Rule's own "unchanged" default for that case -- see
    QueueRebalanceResult's own docstring) rather than corrupting
    anything, so it does not need the durability Commits #1/#2's own
    real domain records do. "Deterministic" (Rule) means what it means
    everywhere else in this series: the same sequence of real state
    changes between calls always produces the same reported drift, not
    that a bare instant snapshot alone determines the result -- a
    rebalancer, by its own nature, is a report of change over time.

    Rank is computed globally, across the whole queue, not only among
    the task_ids considered this call -- a task_id's real position in
    the queue can genuinely shift because of unrelated activity
    elsewhere in the same queue (another task_id enqueued/removed), and
    reporting that faithfully is correct, not spurious. What "Do not
    reorder unrelated queues" rules out is reaching into any *other*
    LLMAgentTaskQueueService instance at all -- structurally impossible
    here, since this class only ever holds the one queue_service (and
    the one reservation_service built over it) it was constructed with.

    Idempotent (Rule): calling rebalance() again immediately, with
    nothing else having changed in between, finds every previously-
    removed task_id already gone (not reconsidered -- it is no longer
    queued at all) and every survivor's rank identical to what the
    prior call just recorded, so everything reports unchanged and
    nothing further is removed.
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
                instance rebalanced -- required, never defaulted.
            readiness_service: The exact Commit #1
                LLMAgentTaskReadinessService instance queue_service
                itself gates enqueue() through -- required, so
                "eligible" always means the same thing here as it does
                at enqueue() time.
            reservation_service: The exact Commit #2
                LLMAgentTaskQueueReservationService instance built over
                queue_service -- required, so "actively reserved" is
                read from the one real reservation store.
            ordering_service: Defaults to a fresh
                LLMAgentTaskQueueOrderingService built *with*
                readiness_service -- deliberately, unlike Commit #4's
                own selection service: rebalance()'s whole point is
                detecting rank drift caused by readiness changes, which
                a readiness-blind ordering could never reflect at all.
        """
        self._queue_service = queue_service
        self._readiness_service = readiness_service
        self._reservation_service = reservation_service
        self._ordering_service = (
            ordering_service if ordering_service is not None else LLMAgentTaskQueueOrderingService(readiness_service)
        )
        self._last_rank: dict[str, int] = {}

    def rebalance(self, task_ids: list = None) -> QueueRebalanceResult:
        """Reconsider task_ids (or, if omitted, every currently queued
        task_id): remove whichever of them are no longer eligible and
        not actively reserved, then report how the remaining ones'
        position has drifted since this instance last observed them.

        Raises:
            InvalidQueueEntryError: If task_ids is given and is not a
                list
        """
        if task_ids is not None and not isinstance(task_ids, list):
            raise InvalidQueueEntryError("task_ids must be a list when given")

        with self._queue_service.atomic():
            initial_order = [entry.task_id for entry in self._ordering_service.order(self._queue_service.store.list())]

            if task_ids is None:
                candidates = initial_order
            else:
                requested = set(task_ids)
                candidates = [task_id for task_id in initial_order if task_id in requested]

            removed = []
            survivors = []
            for task_id in candidates:
                if self._reservation_service.is_reservation_valid(task_id) or self._readiness_service.is_ready(
                    task_id
                ):
                    survivors.append(task_id)
                    continue
                self._queue_service.remove(task_id)
                removed.append(task_id)

            current_order = [entry.task_id for entry in self._ordering_service.order(self._queue_service.store.list())]
            current_rank = {task_id: rank for rank, task_id in enumerate(current_order)}

            reordered = []
            unchanged = []
            for task_id in survivors:
                previous_rank = self._last_rank.get(task_id)
                if previous_rank is not None and previous_rank != current_rank[task_id]:
                    reordered.append(task_id)
                else:
                    unchanged.append(task_id)

            for task_id in removed:
                self._last_rank.pop(task_id, None)
            for task_id in survivors:
                self._last_rank[task_id] = current_rank[task_id]

        return QueueRebalanceResult(
            affected_tasks=candidates,
            reordered_tasks=reordered,
            removed_tasks=removed,
            unchanged_tasks=unchanged,
        )
