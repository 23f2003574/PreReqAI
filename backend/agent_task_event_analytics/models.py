from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass(frozen=True)
class AgentTaskEventAnalytics:
    """LLMAgentTaskEventAnalyticsService.analyze()'s complete, structured
    outcome for one task_id's event stream (or a [start_time, end_time]
    window of it) -- a computed rollup of numbers/durations/timestamps,
    never itself persisted (no to_dict/from_dict round-trip, the same
    "purely computed result" convention backend.agent_task_events'
    own AgentTaskEventReplayResult/AgentTaskEventConsistencyResult already
    establish for a comparable non-persisted result type).

    Deliberately not a second backend.agent_task_events.AgentTaskEventTimeline
    (Rule: "Do not duplicate the timeline service's representation"): there
    is no raw `events` tuple embedded here at all -- every field is either
    a count, a duration, or a single informational timestamp, never the
    ordered event trail itself (a caller who wants that already has
    LLMAgentTaskEventTimelineService.build() for it).

    start_time/end_time echo exactly the bounds analyze() was called with
    (None when omitted), so a caller never has to remember what window a
    given result reflects.

    event_count/event_type_counts/first_event_at/last_event_at are read
    directly off backend.agent_task_events.AgentTaskEventTimeline.build()'s
    own already-computed fields (Rule: "Reuse the existing event query
    service" carried one level further -- reusing Timeline's own
    aggregation instead of re-querying and re-counting a second time).

    state_transition_counts/failure_count are derived from backend.
    agent_task_events.LLMAgentTaskEventReplayService.replay()'s own
    validated state_transitions -- how many times the task's event stream
    actually (legally) transitioned into each backend.agent_task_lifecycle
    STATES value, never a raw, unvalidated count of claimed to_state
    payload values (that distinction matters: an event claiming an
    unreachable or malformed to_state is exactly what Commit #6's own
    replay() already rejects as a replay error, and this service inherits
    that same discipline rather than re-deriving its own).

    time_to_first_event/time_to_terminal_state are both measured from the
    same reference point: the task's own earliest LIFECYCLE_TRANSITIONED
    event whose payload["to_state"] is backend.agent_task_lifecycle.CREATED
    (its "genesis" event) -- the same raw-claimed-to_state convention
    backend.agent_task_events.AgentTaskEventTimeline.current_observed_state
    already uses, not a new one. Both are None whenever that genesis event
    cannot be found in the analyzed window (Rule: "Never infer a duration
    when required boundary events are absent") -- never approximated from
    the first event in the window or from wall-clock time. time_to_terminal_state
    is additionally None whenever the task has not (yet, within this
    window) reached a terminal state at all.

    time_in_state only ever reports durations between two events this
    service actually observed (Rule, again: no inferred duration) -- there
    is deliberately no trailing "time spent in the current/final state
    since it was last observed" entry, since that would require inferring
    an end boundary (now, or the window's own end_time) that no event
    actually marks.

    retry_scheduled_count/retry_cancelled_count are exactly backend.
    agent_task_events.RETRY_SCHEDULED/RETRY_CANCELLED's own counts within
    event_type_counts, exposed directly for convenience (Rule: "Do not
    invent event types that aren't in the repository" -- both are Commit
    #1-of-the-agent-task-events-series' own existing vocabulary, never a
    new "retry" event type).

    terminal_outcome is replay()'s own final_state, but only when that
    value is actually one of backend.agent_task_lifecycle.TERMINAL_STATES
    -- None while the task's observed history has not reached one.
    """

    task_id: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    event_count: int
    event_type_counts: dict
    state_transition_counts: dict
    first_event_at: Optional[datetime]
    last_event_at: Optional[datetime]
    time_to_first_event: Optional[timedelta]
    time_to_terminal_state: Optional[timedelta]
    time_in_state: dict
    retry_scheduled_count: int
    retry_cancelled_count: int
    failure_count: int
    terminal_outcome: Optional[str]
