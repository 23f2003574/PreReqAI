from collections import Counter
from datetime import datetime
from typing import Optional

from backend.agent_task_lifecycle import STATES

from .models import LIFECYCLE_TRANSITIONED, AgentTaskEventTimeline
from .query import LLMAgentTaskEventQueryService


class InvalidAgentTaskEventTimelineError(ValueError):
    """Raised when build() is given invalid arguments."""


class LLMAgentTaskEventTimelineService:
    """Reconstructs one task's chronological progression from its own
    already-persisted AgentTaskEvent stream -- not a second event store or
    a duplicate task-history system (Rule): build() never reads a store
    directly, only Commit #2's own LLMAgentTaskEventQueryService.query(),
    the same "reuse existing authorization/scope filtering" this family's
    every read path already establishes -- there is nothing narrower than
    that query service's own filtering to bypass or reimplement.

    Read-only: build() has no counterpart that writes, emits, or executes
    anything, and never calls backend.agent_task_lifecycle.
    LLMAgentTaskLifecycleService.transition() or any other mutating method
    anywhere in this task family.

    Ordering is entirely Commit #2's own (Rule: "Order them chronologically
    with deterministic tie-breaking" is satisfied by delegating to query(),
    never a second sort implemented here) -- build() only ever summarizes
    the list query() already returned in the right order.

    current_observed_state derivation (see AgentTaskEventTimeline's own
    docstring) only ever considers LIFECYCLE_TRANSITIONED events whose own
    payload["to_state"] is a recognized backend.agent_task_lifecycle.STATES
    value -- every other event_type, and every LIFECYCLE_TRANSITIONED event
    with a missing/unrecognized payload, is simply skipped rather than
    guessed at (Rule: "Do not invent missing state from incomplete
    events"). Processing events in their own chronological order and only
    ever overwriting the running result on a *valid* sighting means one
    malformed event in the middle of an otherwise coherent trail can never
    erase a real, earlier observation.
    """

    def __init__(self, query_service: LLMAgentTaskEventQueryService = None):
        self._query_service = query_service if query_service is not None else LLMAgentTaskEventQueryService()

    def build(
        self, task_id: str, start_time: datetime = None, end_time: datetime = None
    ) -> AgentTaskEventTimeline:
        """task_id's timeline over its persisted events, optionally
        narrowed to [start_time, end_time] (either bound may be omitted).

        Never raises for a task_id with no recorded events: an empty
        timeline (event_count=0, first/last_event_at=None,
        current_observed_state=None) is a valid result (Rule: "Empty
        timelines are valid results"), exactly as for a task_id that was
        never emitted for at all -- this service holds no opinion on task
        identity, the same discipline every other read path in this
        family already establishes.

        Raises:
            InvalidAgentTaskEventTimelineError: If task_id is not a
                non-empty string
            InvalidAgentTaskEventQueryError: If start_time/end_time is
                given and is not a datetime (Commit #2's own
                query()/error, propagated unchanged)
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventTimelineError("task_id is required and must be a non-empty string")

        events = self._query_service.query(task_id=task_id, start_time=start_time, end_time=end_time)

        return AgentTaskEventTimeline(
            task_id=task_id,
            events=tuple(events),
            first_event_at=events[0].occurred_at if events else None,
            last_event_at=events[-1].occurred_at if events else None,
            event_count=len(events),
            event_type_counts=dict(Counter(event.event_type for event in events)),
            current_observed_state=self._derive_current_observed_state(events),
        )

    @staticmethod
    def _derive_current_observed_state(events) -> Optional[str]:
        current_observed_state = None
        for event in events:
            if event.event_type != LIFECYCLE_TRANSITIONED:
                continue
            if not isinstance(event.payload, dict):
                continue
            to_state = event.payload.get("to_state")
            if isinstance(to_state, str) and to_state in STATES:
                current_observed_state = to_state
        return current_observed_state
