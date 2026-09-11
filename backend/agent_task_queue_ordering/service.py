from typing import Optional

from backend.agent_task_queue import InvalidQueueEntryError, QueueEntry
from backend.agent_task_readiness import LLMAgentTaskReadinessService


class LLMAgentTaskQueueOrderingService:
    """Deterministic, read-only ordering over Commit #1 QueueEntry
    records -- not a second queue or scheduler (Rule: "do not create
    another queue or scheduling system"): this service never persists
    anything, never mutates an entry (QueueEntry is already frozen --
    see Commit #1's own model -- so there is nothing in-place to
    mutate), and never claims or executes anything. It only ever
    answers "given these entries, what order should they be considered
    in."

    Precedence (Goal): readiness -> priority -> queued_at -> task_id.
    Priority/queued_at/task_id are exactly Commit #1's own QueueEntry
    fields and exactly the (-priority, queued_at, task_id) tie-break
    LLMAgentTaskQueueService.peek() already used -- reused verbatim here
    (Rule: "do not duplicate priority definitions already owned
    elsewhere"), never redefined.

    readiness is included only when a readiness_service is actually
    supplied (Rule: "only include readiness ... if the existing task
    model exposes it") -- reusing backend.agent_task_readiness.
    LLMAgentTaskReadinessService.is_ready(), the exact same readiness
    gate Commit #1's own enqueue() already uses, rather than a second
    notion of ready. This matters beyond enqueue time: nothing in this
    queue ever removes an entry when its task later stops being ready
    (Commit #1 has no such polling/eviction, and Rule: "Queue state is
    not task lifecycle state" means it never will), so a queue can
    accumulate entries for tasks that were ready when enqueued but are
    not ready any more (e.g. one dependency later failed, or the task
    itself moved on to RUNNING already). Ordering ready entries first is
    what keeps peek()/next() surfacing genuinely actionable work despite
    that. Without a readiness_service, this criterion is skipped
    entirely -- every entry is treated as equally "not ranked" by
    readiness, exactly as if the criterion were absent.

    order()/compare() share one implementation of "what order do these
    go in" (_sort_key()) so the two can never disagree about the same
    entries -- compare(a, b) is computed from exactly the same key
    order() itself sorts by. Same inputs always produce the same output
    (Rule: "Same inputs must always produce the same ordering") since
    _sort_key() is a pure function of an entry's own already-immutable
    fields plus, when configured, one live is_ready() read -- itself a
    read-only, side-effect-free check (see LLMAgentTaskReadinessService's
    own docstring: "never mutates, schedules, executes, or repairs").
    """

    def __init__(self, readiness_service: LLMAgentTaskReadinessService = None):
        """
        Args:
            readiness_service: Optional backend.agent_task_readiness.
                LLMAgentTaskReadinessService -- when given, readiness
                becomes this ordering's own first, highest-precedence
                criterion (ready entries before not-ready ones). Omit
                to order purely by priority/queued_at/task_id, with no
                readiness criterion at all.
        """
        self._readiness_service = readiness_service

    def order(self, entries: list) -> list:
        """entries, re-ordered by this service's own deterministic
        precedence. Always returns a new list -- entries itself (and
        every QueueEntry in it) is left completely unchanged (Rule:
        "Never mutate queue entries").

        Raises:
            InvalidQueueEntryError: If entries is not a list, or
                contains anything other than QueueEntry instances
        """
        self._validate_entries(entries)
        return sorted(entries, key=self._sort_key)

    def next(self, entries: list) -> Optional[QueueEntry]:
        """The single entry order(entries) would place first, or None
        if entries is empty. Never claims or otherwise acts on it --
        purely a read (Rule: "Never execute or claim tasks")."""
        ordered = self.order(entries)
        return ordered[0] if ordered else None

    def compare(self, left: QueueEntry, right: QueueEntry) -> int:
        """-1 if left sorts before right, 1 if left sorts after right,
        0 if they are equivalent under this ordering (in practice, only
        when left and right share the same task_id -- Commit #1's own
        store never holds two live entries for the same task_id).

        Raises:
            InvalidQueueEntryError: If left or right is not a QueueEntry
        """
        self._validate_entry(left, "left")
        self._validate_entry(right, "right")

        left_key = self._sort_key(left)
        right_key = self._sort_key(right)
        if left_key < right_key:
            return -1
        if left_key > right_key:
            return 1
        return 0

    def _sort_key(self, entry: QueueEntry) -> tuple:
        base = (-entry.priority, entry.queued_at, entry.task_id)
        if self._readiness_service is None:
            return base
        readiness_rank = 0 if self._readiness_service.is_ready(entry.task_id) else 1
        return (readiness_rank,) + base

    @staticmethod
    def _validate_entries(entries) -> None:
        if not isinstance(entries, list):
            raise InvalidQueueEntryError("entries must be a list")
        for entry in entries:
            LLMAgentTaskQueueOrderingService._validate_entry(entry, "entries")

    @staticmethod
    def _validate_entry(entry, field_name: str) -> None:
        if not isinstance(entry, QueueEntry):
            raise InvalidQueueEntryError(f"{field_name} must contain only QueueEntry instances")
