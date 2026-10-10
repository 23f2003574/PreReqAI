from collections.abc import Iterable
from datetime import datetime
from typing import Optional

from .in_memory_store import InMemoryAgentTaskEventStore
from .store import AgentTaskEventStore


class InvalidAgentTaskEventQueryError(ValueError):
    """Raised when query()/count() is given invalid arguments."""


class LLMAgentTaskEventQueryService:
    """Read-only filtering over Commit #1's own AgentTaskEvent stream --
    not a second event store or a generic query framework (Rule): every
    call reads through this module's own AgentTaskEventStore
    (list_for_task()/all()), and every filter here (event_types/time
    range/limit) is something that store deliberately does not know how
    to do itself, the same "filtering happens in the service layer, the
    store only stores" split Commit #1's own LLMAgentTaskEventService.get()
    already established for its own (single) event_type filter.

    query()/count() never emit, mutate, or execute anything -- they are
    the only two public methods this service has, and neither ever calls
    LLMAgentTaskEventService.emit() or any store's save().

    AgentTaskEvent carries no scope/authorization field of its own (see
    Commit #1's own models.py) and Commit #1 established no access-control
    concept for it -- so "preserve existing authorization/scope rules"
    means exactly that: there is none to preserve, and this service
    invents none of its own. It also holds no opinion on task identity,
    the same discipline every other read path in this family already
    established: querying with an unknown task_id, or one that matches
    nothing, is simply an empty result, never an error.

    Ordering is always oldest to newest across every query (Rule:
    "Preserve append order/timestamps"), broken by (task_id, event_id)
    only for the deterministic edge case of two events sharing an
    occurred_at exactly (Rule: "deterministic ordering") -- this
    additional tie-break is this service's own, layered on top of what
    each store already guarantees for a single task's list (sorted by
    occurred_at alone), since merging multiple tasks' own lists for a
    cross-task query can otherwise not be fully deterministic.

    limit caps results to the most recent `limit` matches (still returned
    oldest to newest) -- the same convention Commit #1's own get(limit=)
    already chose, reused here rather than re-decided.
    """

    def __init__(self, store: AgentTaskEventStore = None):
        self.store = store if store is not None else InMemoryAgentTaskEventStore()

    def query(
        self,
        task_id: str = None,
        event_types=None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = None,
    ) -> list:
        """Every persisted event matching the given filters, oldest to
        newest. Every filter is optional; query() with no arguments
        returns every event ever recorded, across every task.

        Raises:
            InvalidAgentTaskEventQueryError: If task_id is given and is
                not a non-empty string, event_types is given and is not
                an iterable of non-empty strings, start_time/end_time is
                given and is not a datetime, or limit is given and is not
                a non-negative int
        """
        if task_id is not None:
            self._require_text(task_id, "task_id")
        event_type_set = self._normalize_event_types(event_types)
        if start_time is not None and not isinstance(start_time, datetime):
            raise InvalidAgentTaskEventQueryError("start_time must be a datetime when given")
        if end_time is not None and not isinstance(end_time, datetime):
            raise InvalidAgentTaskEventQueryError("end_time must be a datetime when given")
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise InvalidAgentTaskEventQueryError("limit must be a non-negative int when given")

        events = self.store.list_for_task(task_id) if task_id is not None else self.store.all()

        if event_type_set is not None:
            events = [event for event in events if event.event_type in event_type_set]
        if start_time is not None:
            events = [event for event in events if event.occurred_at >= start_time]
        if end_time is not None:
            events = [event for event in events if event.occurred_at <= end_time]

        events = sorted(events, key=lambda event: (event.occurred_at, event.task_id, event.event_id))

        if limit is not None:
            events = events[-limit:] if limit > 0 else []

        return events

    def count(self, task_id: str = None, event_types=None) -> int:
        """The number of persisted events matching the given filters --
        exactly len(self.query(task_id=task_id, event_types=event_types)),
        never a separately maintained tally (Rule: "Count matches query
        semantics").

        Raises the same errors query() raises for these same arguments.
        """
        return len(self.query(task_id=task_id, event_types=event_types))

    @staticmethod
    def _normalize_event_types(event_types) -> Optional[frozenset]:
        if event_types is None:
            return None
        if isinstance(event_types, str) or not isinstance(event_types, Iterable):
            raise InvalidAgentTaskEventQueryError(
                "event_types must be an iterable of non-empty strings when given"
            )
        normalized = []
        for event_type in event_types:
            if not event_type or not isinstance(event_type, str):
                raise InvalidAgentTaskEventQueryError("event_types must contain only non-empty strings")
            normalized.append(event_type)
        return frozenset(normalized)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskEventQueryError(f"{field_name} is required and must be a non-empty string")
