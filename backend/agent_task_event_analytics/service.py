from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from backend.agent_task_events import (
    LIFECYCLE_TRANSITIONED,
    RETRY_CANCELLED,
    RETRY_SCHEDULED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventReplayService,
    LLMAgentTaskEventTimelineService,
)
from backend.agent_task_lifecycle import CREATED, FAILED, TERMINAL_STATES

from .models import AgentTaskEventAnalytics


class InvalidAgentTaskEventAnalyticsError(ValueError):
    """Raised when analyze() is given invalid arguments."""


class LLMAgentTaskEventAnalyticsService:
    """Computes task-focused analytics (durations, transition counts,
    terminal outcomes, retry patterns) over the existing
    backend.agent_task_events event stream -- a new analytical layer, not
    another event viewer (Rule): analyze() never queries, sorts, or
    validates an event stream itself; it composes exactly two existing
    services and rolls their own already-computed answers into one result.

    Composes, never duplicates (Rule: "Do not create another event store,
    observability system, or timeline implementation"):
      - backend.agent_task_events.LLMAgentTaskEventTimelineService.build()
        supplies event_count/event_type_counts/first_event_at/
        last_event_at and the ordered event list used internally to find
        the genesis event -- the raw event tuple itself is never
        re-exposed on AgentTaskEventAnalytics (see that class's own
        docstring for why).
      - backend.agent_task_events.LLMAgentTaskEventReplayService.replay()
        supplies state_transitions/final_state -- the authoritative,
        already-validated source for every transition-count and terminal-
        outcome question this service answers; an event claiming an
        unreachable or malformed to_state is exactly what replay() already
        rejects, and this service never re-derives its own opinion about
        that.

    Read-only: analyze() never calls emit()/save()/delete() anywhere, and
    the two collaborators it composes are themselves already read-only.

    Deterministic (Rule): both Timeline and Replay are already
    deterministic over a fixed event stream, and every aggregation here
    (Counter, boundary sort) is a pure function of their own outputs, with
    no randomness or wall-clock dependency beyond echoing the caller's own
    start_time/end_time arguments back in the result.
    """

    def __init__(
        self,
        query_service: LLMAgentTaskEventQueryService = None,
        timeline_service: LLMAgentTaskEventTimelineService = None,
        replay_service: LLMAgentTaskEventReplayService = None,
    ):
        self._query_service = query_service if query_service is not None else LLMAgentTaskEventQueryService()
        self._timeline_service = (
            timeline_service
            if timeline_service is not None
            else LLMAgentTaskEventTimelineService(self._query_service)
        )
        self._replay_service = (
            replay_service if replay_service is not None else LLMAgentTaskEventReplayService(self._query_service)
        )

    def analyze(
        self, task_id: str, start_time: datetime = None, end_time: datetime = None
    ) -> AgentTaskEventAnalytics:
        """Compute task_id's event-stream analytics, optionally narrowed
        to [start_time, end_time].

        Never raises for a task_id with no recorded events: a clean,
        fully-populated result (every count 0, every duration/timestamp
        None) -- this service holds no opinion on task identity, the same
        discipline every other read path in this family already
        establishes.

        Raises:
            InvalidAgentTaskEventAnalyticsError: If task_id is not a
                non-empty string
            InvalidAgentTaskEventQueryError: If start_time/end_time is
                given and is not a datetime (Commit #2-of-the-agent-task-
                events-series' own query()/error, propagated unchanged)
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventAnalyticsError("task_id is required and must be a non-empty string")

        timeline = self._timeline_service.build(task_id, start_time=start_time, end_time=end_time)
        replay_result = self._replay_service.replay(task_id, start_time=start_time, end_time=end_time)

        events_by_id = {event.event_id: event for event in timeline.events}
        genesis_event = self._find_genesis_event(timeline.events)

        state_transition_counts = dict(
            Counter(transition.to_state for transition in replay_result.state_transitions)
        )

        time_to_first_event = None
        if genesis_event is not None and timeline.events:
            time_to_first_event = timeline.events[0].occurred_at - genesis_event.occurred_at

        terminal_outcome = replay_result.final_state if replay_result.final_state in TERMINAL_STATES else None

        time_to_terminal_state = None
        if terminal_outcome is not None and genesis_event is not None and replay_result.state_transitions:
            terminal_event = events_by_id.get(replay_result.state_transitions[-1].event_id)
            if terminal_event is not None:
                time_to_terminal_state = terminal_event.occurred_at - genesis_event.occurred_at

        time_in_state = self._time_in_state(replay_result.state_transitions, events_by_id, genesis_event)

        return AgentTaskEventAnalytics(
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            event_count=timeline.event_count,
            event_type_counts=dict(timeline.event_type_counts),
            state_transition_counts=state_transition_counts,
            first_event_at=timeline.first_event_at,
            last_event_at=timeline.last_event_at,
            time_to_first_event=time_to_first_event,
            time_to_terminal_state=time_to_terminal_state,
            time_in_state=time_in_state,
            retry_scheduled_count=timeline.event_type_counts.get(RETRY_SCHEDULED, 0),
            retry_cancelled_count=timeline.event_type_counts.get(RETRY_CANCELLED, 0),
            failure_count=state_transition_counts.get(FAILED, 0),
            terminal_outcome=terminal_outcome,
        )

    @staticmethod
    def _find_genesis_event(events):
        for event in events:
            if event.event_type != LIFECYCLE_TRANSITIONED:
                continue
            to_state = event.payload.get("to_state") if isinstance(event.payload, dict) else None
            if to_state == CREATED:
                return event
        return None

    @staticmethod
    def _time_in_state(transitions, events_by_id: dict, genesis_event) -> dict:
        boundaries = []
        if genesis_event is not None:
            boundaries.append((genesis_event.occurred_at, CREATED))
        for transition in transitions:
            event = events_by_id.get(transition.event_id)
            if event is None:
                continue
            boundaries.append((event.occurred_at, transition.to_state))

        boundaries.sort(key=lambda boundary: boundary[0])

        time_in_state: dict = {}
        for (start, state), (end, _next_state) in zip(boundaries, boundaries[1:]):
            time_in_state[state] = time_in_state.get(state, timedelta()) + (end - start)
        return time_in_state
