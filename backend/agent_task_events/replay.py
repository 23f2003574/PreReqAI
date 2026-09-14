from backend.agent_task_lifecycle import CREATED, STATES, LLMAgentTaskLifecycleService

from .models import (
    LIFECYCLE_TRANSITIONED,
    AgentTaskEventReplayFailure,
    AgentTaskEventReplayResult,
    AgentTaskStateTransition,
)
from .query import LLMAgentTaskEventQueryService


class InvalidAgentTaskEventReplayError(ValueError):
    """Raised when replay() is given invalid arguments."""


class LLMAgentTaskEventReplayService:
    """Reconstructs a task's own lifecycle state purely by replaying its
    persisted event stream -- the first real event-to-state reconstruction
    layer in this series (Commits #2/#3 only ever queried/summarized
    already-claimed values; this one actually walks the chain and decides,
    event by event, whether each claimed transition was legal from
    wherever replay's own running state currently is).

    Not a second task state machine (Rule): every legality check delegates
    to backend.agent_task_lifecycle.LLMAgentTaskLifecycleService.
    can_transition() -- the one authoritative transition definition this
    entire task family already shares (the same reuse Commit #5's own
    LLMAgentTaskEventConsistencyService already established) -- and
    initial_state/STATES are that same module's own constants, imported
    rather than redeclared.

    Deliberately does NOT duplicate Commit #3's own
    LLMAgentTaskEventTimelineService (Rule: "Do not duplicate the timeline
    service; replay must actually reconstruct transitions/state"):
    Timeline.current_observed_state is a best-effort "last valid sighting"
    scan that never validates *reachability* between sightings and never
    reports a failure; replay() is the opposite in both respects -- it
    tracks a running state and rejects (as a replay_error, leaving the
    running state unchanged) any claimed to_state that is not actually
    reachable via can_transition() from wherever replay currently is.

    Deliberately does NOT take a lifecycle_service collaborator at all
    (unlike Commit #5's consistency service): replay reconstructs state
    from the event stream alone, never cross-checking or reading
    authoritative backend.agent_task_lifecycle state -- that comparison is
    Commit #5's own STATE_MISMATCH job, not this one's (Rule: "reconstructs
    the task's observed event state from its event stream").

    Read-only: replay() never calls transition()/emit()/update() on
    anything, and never persists its own result -- every AgentTask/
    AgentTaskEvent record involved is left exactly as it already was.

    Reuses Commit #2's own query_service (Rule: "Reuse Commit #2 querying
    rather than directly duplicating storage access") for both the
    chronological ordering and the [start_time, end_time] windowing --
    replay() never touches a store directly.
    """

    def __init__(self, query_service: LLMAgentTaskEventQueryService = None):
        self._query_service = query_service if query_service is not None else LLMAgentTaskEventQueryService()

    def replay(self, task_id: str, start_time=None, end_time=None) -> AgentTaskEventReplayResult:
        """Reconstruct task_id's own state by replaying its persisted
        events (optionally narrowed to [start_time, end_time]) in
        chronological order, starting from CREATED.

        For each LIFECYCLE_TRANSITIONED event, in order:
          - a payload with no to_state at all is skipped (still counted in
            events_replayed) -- Rule: "Do not reject legitimate legacy
            events merely because optional metadata is absent" (carried
            forward from Commits #3/#5)
          - a to_state that is not a recognized
            backend.agent_task_lifecycle.STATES value is a replay_error
            ("cannot be applied": malformed data, not merely-absent
            metadata)
          - a recognized to_state that is not reachable from replay's own
            current running state via can_transition() is a replay_error;
            the running state is left unchanged (Rule: "instead of
            silently inventing a state")
          - a recognized, reachable to_state equal to the running state
            (a legal self-transition/reaffirmation) updates nothing
            further and is not recorded as a state_transition -- the same
            "a repeated same-state move is a no-op, not a real
            transition" convention
            backend.agent_task_lifecycle.LLMAgentTaskLifecycleService.
            transition() itself already establishes
          - any other recognized, reachable, different to_state is
            applied: recorded in state_transitions and becomes the new
            running state

        Every other event_type is counted in events_replayed and
        otherwise ignored entirely (Rule: "apply only event types that
        the repository already defines as state-bearing").

        Never raises for a task_id with no recorded events: an empty,
        fully-valid result (initial_state == final_state == CREATED,
        no transitions, no errors) -- this service holds no opinion on
        task identity, the same discipline every other read path in this
        family already establishes.

        Raises:
            InvalidAgentTaskEventReplayError: If task_id is not a
                non-empty string
            InvalidAgentTaskEventQueryError: If start_time/end_time is
                given and is not a datetime (Commit #2's own query()/
                error, propagated unchanged)
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventReplayError("task_id is required and must be a non-empty string")

        events = self._query_service.query(task_id=task_id, start_time=start_time, end_time=end_time)

        running_state = CREATED
        transitions = []
        errors = []

        for event in events:
            if event.event_type != LIFECYCLE_TRANSITIONED:
                continue

            to_state = event.payload.get("to_state") if isinstance(event.payload, dict) else None
            if to_state is None:
                continue

            if to_state not in STATES:
                errors.append(
                    AgentTaskEventReplayFailure(
                        event_id=event.event_id,
                        reason=f"declares to_state {to_state!r}, which is not a recognized lifecycle state",
                    )
                )
                continue

            if not LLMAgentTaskLifecycleService.can_transition(running_state, to_state):
                errors.append(
                    AgentTaskEventReplayFailure(
                        event_id=event.event_id,
                        reason=f"cannot transition from {running_state!r} to {to_state!r}",
                    )
                )
                continue

            if to_state == running_state:
                continue

            transitions.append(
                AgentTaskStateTransition(from_state=running_state, to_state=to_state, event_id=event.event_id)
            )
            running_state = to_state

        return AgentTaskEventReplayResult(
            task_id=task_id,
            events_replayed=len(events),
            initial_state=CREATED,
            final_state=running_state,
            state_transitions=tuple(transitions),
            replay_errors=tuple(errors),
        )
