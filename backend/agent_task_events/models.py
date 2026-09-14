from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Well-known event_type vocabulary, scoped only to concepts that already exist
# elsewhere in this task family (Rule: "Support meaningful task events ... only
# where those concepts already exist"): backend.agent_task_lifecycle's own
# transitions, backend.agent_task_dependencies' own edges, backend.
# agent_task_readiness/agent_task_readiness_projection's own readiness
# outcome, backend.agent_task_queue_retry_scheduler's own schedules, and
# backend.agent_task_context's own package updates.
#
# emit() does not restrict event_type to this set -- these are documented,
# not enforced, the same "known key vocabulary, not a closed enum" discipline
# backend.agent_task_queue_retry_eligibility's own docstring already uses for
# AgentTask.definition's keys -- so a future commit can introduce another
# meaningful event_type without this module needing to change. Keeping emit()
# itself open also avoids this module becoming a second, competing state
# machine over event_type the way a closed STATES-style enum would.
LIFECYCLE_TRANSITIONED = "lifecycle_transitioned"
DEPENDENCY_ADDED = "dependency_added"
DEPENDENCY_REMOVED = "dependency_removed"
READINESS_CHANGED = "readiness_changed"
RETRY_SCHEDULED = "retry_scheduled"
RETRY_CANCELLED = "retry_cancelled"
CONTEXT_UPDATED = "context_updated"

# Commit #4's own addition: the marker event LLMAgentTaskEventCorrelationService.
# correlate() emits. A genuinely new concept (correlation itself), not one
# borrowed from an existing task-family service the way the seven event types
# above are -- exactly the kind of extension this vocabulary's own "documented,
# not enforced" design already anticipated.
CORRELATION_ESTABLISHED = "correlation_established"

KNOWN_EVENT_TYPES = frozenset(
    {
        LIFECYCLE_TRANSITIONED,
        DEPENDENCY_ADDED,
        DEPENDENCY_REMOVED,
        READINESS_CHANGED,
        RETRY_SCHEDULED,
        RETRY_CANCELLED,
        CONTEXT_UPDATED,
        CORRELATION_ESTABLISHED,
    }
)


@dataclass(frozen=True)
class AgentTaskEvent:
    """One immutable, append-only entry in a task's own event stream.

    Deliberately not a second lifecycle/history record (Rule: "Do not
    duplicate lifecycle/history state as a second source of truth"): this
    module holds no opinion on whether a task, dependency, or schedule
    actually exists, and never reads or recomputes state from
    backend.agent_task_lifecycle/agent_task_state_history/
    agent_task_dependencies/agent_task_readiness/agent_task_queue_retry_*/
    agent_task_context itself. A caller that owns one of those concepts
    (a future commit's own tracked-style wrapper -- see backend.
    agent_task_state_history.tracked for the shape that precedent already
    takes) is responsible for calling emit() after its own change actually
    happened; this event is only ever the durable record that it did.

    payload is a small, caller-supplied dict of references/metadata about
    the event -- ids, keys, counts, before/after state labels -- never a
    duplicated copy of a large or sensitive record that already has a
    canonical home elsewhere (Rule: "Prefer references/metadata over
    duplicating large or sensitive payloads"), the same "ids and labels,
    never raw content" discipline backend.agent_task_context_provenance.
    ContextProvenanceRecord and backend.agent_task_queue_dead_letter.
    DeadLetterEntry.metadata already establish for comparable records in
    this same project. LLMAgentTaskEventService redacts it through this
    repository's own canonical backend.llm.secret_redaction.
    LLMSecretRedactionService before it is ever stored, the same reused
    safeguard backend.agent_capability_execution/backend.
    agent_task_context_integrity already apply to their own payloads,
    rather than a new redaction/size-limiting scheme invented here.

    Field names deliberately follow this task family's own established
    vocabulary rather than the goal's literal wording: event_id (not
    "id"), matching TaskTransitionRecord.transition_id; occurred_at (not
    "timestamp"), matching TaskTransitionRecord.occurred_at/
    DeadLetterEntry.failed_at.

    correlation_id/parent_event_id/operation_id (Commit #4) are plain,
    optional reference fields, deliberately not a second, heavier
    span/status tracing record like backend.session.execution_trace.
    ExecutionTrace (Rule: "Do not introduce distributed tracing
    infrastructure" / "Do not invent a parallel tracing system") -- there
    is no started_at/finished_at/status lifecycle here, just three bare
    identifiers a caller may attach to relate events to each other or to
    one logical operation, the same "ids and labels, never raw content"
    discipline this event's own payload field already follows (Rule:
    "Correlation metadata must reference events/operations, not
    duplicate payloads"). All three default to None and are never
    required, so every event Commits #1-#3 already emitted (with no
    knowledge of these fields at all) still round-trips through to_dict()/
    from_dict() unchanged (Rule: "Existing events without correlation
    metadata remain valid").
    """

    task_id: str
    event_type: str
    payload: Optional[dict] = None
    correlation_id: Optional[str] = None
    parent_event_id: Optional[str] = None
    operation_id: Optional[str] = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["occurred_at"] = self.occurred_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskEvent":
        payload = dict(data)
        value = payload.get("occurred_at")
        if isinstance(value, str):
            payload["occurred_at"] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskEventTimeline:
    """One task's chronological progression, reconstructed entirely from
    its own already-persisted AgentTaskEvent stream by Commit #3's
    LLMAgentTaskEventTimelineService.build() -- a computed, read-only view,
    never itself persisted (no store/to_dict round-trip is needed the way
    AgentTaskEvent's own is, since nothing ever writes a timeline back;
    to_dict() exists purely for callers that want a serializable snapshot).

    events is a tuple (not a list) -- the same structural-immutability
    discipline backend.agent_task_context_provenance.ContextProvenanceRecord.
    entries already establishes -- holding the exact AgentTaskEvent records
    LLMAgentTaskEventQueryService.query() returned, never reshaped or
    copied into a second representation (Rule: "Preserve event payload/
    reference data without duplicating it").

    current_observed_state is explicitly *observed*, not authoritative
    (Rule: "Do not replace authoritative task state with the timeline"):
    it is whatever backend.agent_task_lifecycle.STATES value the most
    recent LIFECYCLE_TRANSITIONED event's own payload["to_state"]
    reported, or None if no event in this timeline ever reported one
    (Rule: "Do not invent missing state from incomplete events") -- the
    real, authoritative current_state still lives only in
    backend.agent_task_lifecycle.AgentTask itself.
    """

    task_id: str
    events: tuple
    first_event_at: Optional[datetime]
    last_event_at: Optional[datetime]
    event_count: int
    event_type_counts: dict
    current_observed_state: Optional[str]

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "events": [event.to_dict() for event in self.events],
            "first_event_at": self.first_event_at.isoformat() if self.first_event_at else None,
            "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None,
            "event_count": self.event_count,
            "event_type_counts": dict(self.event_type_counts),
            "current_observed_state": self.current_observed_state,
        }


# Commit #5's own violation-category vocabulary -- a closed set (unlike
# KNOWN_EVENT_TYPES) since these six are exactly the categories the goal
# itself names; LLMAgentTaskEventConsistencyService.validate() never reports
# a category outside this set.
IMPOSSIBLE_TRANSITION = "impossible_transition"
INVALID_ORDER = "invalid_order"
CONFLICTING_TERMINAL = "conflicting_terminal"
MISSING_REFERENCE = "missing_reference"
STATE_MISMATCH = "state_mismatch"
INVALID_RELATIONSHIP = "invalid_relationship"

CONSISTENCY_VIOLATION_CATEGORIES = frozenset(
    {
        IMPOSSIBLE_TRANSITION,
        INVALID_ORDER,
        CONFLICTING_TERMINAL,
        MISSING_REFERENCE,
        STATE_MISMATCH,
        INVALID_RELATIONSHIP,
    }
)


@dataclass(frozen=True)
class AgentTaskEventConsistencyViolation:
    """One concrete inconsistency LLMAgentTaskEventConsistencyService.
    validate() found, always anchored to the one event responsible for it.

    event_id is a reference, not the event itself (Rule: "Correlation
    metadata must reference events/operations, not duplicate payloads" --
    the same "ids and labels, never raw content" discipline this whole
    module already applies to payload/correlation fields extends here too):
    a caller who wants the full AgentTaskEvent already has it, from the
    same query() call validate() itself used.
    """

    event_id: str
    category: str
    reason: str


@dataclass(frozen=True)
class AgentTaskEventConsistencyResult:
    """LLMAgentTaskEventConsistencyService.validate()'s complete,
    structured outcome for one task's event stream.

    Deterministic and side-effect free (Rule: "Deterministic results"):
    computing a result never mutates, persists, or emits anything, and the
    same persisted events always produce the same violations in the same
    order (every check below iterates Commit #2's own already-
    deterministically-ordered query() result in a fixed sequence).

    is_consistent is exactly `not violations` -- the same
    `valid = not errors` convention
    backend.agent_task_state_validation.AgentTaskStateValidationResult
    already establishes for a comparable "consistency of one entity"
    result.

    checked_task_state is backend.agent_task_lifecycle.AgentTask's own
    current_state at validation time -- the authoritative value every
    STATE_MISMATCH violation compares an event-derived observation
    against, exposed here so a caller never has to re-fetch it separately.
    """

    task_id: str
    is_consistent: bool
    violations: tuple
    checked_event_count: int
    checked_task_state: Optional[str]


@dataclass(frozen=True)
class AgentTaskStateTransition:
    """One state-bearing move LLMAgentTaskEventReplayService.replay()
    actually applied while reconstructing a task's state -- from_state is
    always whatever replay's own running state was immediately before this
    event, never a value read off the event's own payload (Commit #1's
    AgentTaskEvent payload only ever records to_state, the same convention
    Commit #3's own current_observed_state derivation already established);
    this is what makes replay an actual reconstruction rather than a replay
    of already-claimed transitions.
    """

    from_state: str
    to_state: str
    event_id: str


@dataclass(frozen=True)
class AgentTaskEventReplayFailure:
    """One state-bearing event replay() could not apply -- reported
    instead of silently inventing a state (Rule: "Report invalid
    transitions as replay errors instead of silently inventing a state").
    event_id is a reference, the same "ids and labels, never the object
    itself" discipline every other result type in this module already
    follows.
    """

    event_id: str
    reason: str


@dataclass(frozen=True)
class AgentTaskEventReplayResult:
    """LLMAgentTaskEventReplayService.replay()'s complete, structured
    outcome for one task's event stream (or a [start_time, end_time]
    window of it).

    initial_state is always backend.agent_task_lifecycle.CREATED -- the
    one canonical starting state every real AgentTask actually begins in
    (Commit #1's own default), and the only starting point replay can
    assume without consulting authoritative state it is deliberately not
    given (Rule: "reconstructs ... from its event stream," not by cross-
    checking backend.agent_task_lifecycle -- that cross-check is Commit
    #5's own STATE_MISMATCH job, not this one's). A window whose start_time
    excludes a task's own earlier lifecycle events therefore may report
    replay_errors for transitions that were legal in full history but
    look unreachable from the assumed CREATED starting point within this
    narrower window -- an inherent, documented limitation of windowed
    replay from a fixed assumed origin, not a defect.

    events_replayed counts every event replay() considered in the window,
    state-bearing or not (Rule: "Unknown/non-state-bearing events should
    remain in the replay count but not fabricate state changes") --
    state_transitions/replay_errors only ever reflect LIFECYCLE_TRANSITIONED
    events with a recognized to_state.

    Deterministic (Rule): the same persisted events in the same window
    always replay to the same final_state/state_transitions/replay_errors,
    since replay walks Commit #2's own already-deterministically-ordered
    query() result exactly once, in order, with no randomness or wall-
    clock dependency of its own.
    """

    task_id: str
    events_replayed: int
    initial_state: str
    final_state: str
    state_transitions: tuple
    replay_errors: tuple


@dataclass(frozen=True)
class AgentTaskEventProjection:
    """A queryable, current-state read model for one task_id, entirely
    derived from its own persisted event stream -- never a second source
    of truth (Rule: "Do not make the projection authoritative task
    state"; "Keep the projection explicitly derived/read-only from the
    authoritative event stream"). The real authority for lifecycle state
    remains backend.agent_task_lifecycle.AgentTask, exactly as Commits
    #3/#5/#6 already establish for their own event-derived views.

    Exactly one of these exists per task_id at a time -- the same
    "replace, don't accumulate" shape
    backend.agent_task_readiness_projection.AgentTaskReadinessProjection
    already established for a comparable "latest known derived view"
    record in this project (the closest existing projection/read-model
    pattern found by this commit's own "check whether one already
    exists" inspection step) -- deliberately reused for persistence
    shape (a plain save()/get() store, not an append-only trail), while
    the split into project()/refresh()/get() (see
    LLMAgentTaskEventProjectionService) is new to this module: that
    precedent conflates "compute" and "persist" into one project() call,
    but this goal names three distinct operations, so they are kept
    distinct here rather than collapsed to match that precedent exactly.

    current_state/last_error_reference are never independently derived:
    both come from a single Commit #6 LLMAgentTaskEventReplayService.
    replay() call (Rule: "Reuse Commit #6 replay semantics ... instead
    of duplicating transition logic") -- current_state is that result's
    own final_state, and last_error_reference is the event_id of its
    most recent replay_errors entry (or None if replay reported none).
    last_event_id/last_event_at/event_count come from a single Commit #3
    LLMAgentTaskEventTimelineService.build() call (Rule: "Do not create
    another timeline/query implementation") rather than a third,
    separately-sorted read of the event stream.

    active_retry_reference/active_context_reference are plain references
    (event_id), not duplicated event content (the same "ids and labels,
    never raw content" discipline every result type in this module
    already follows): active_retry_reference is the most recent
    RETRY_SCHEDULED event's event_id, unless a later RETRY_CANCELLED
    event has since superseded it (then None); active_context_reference
    is simply the most recent CONTEXT_UPDATED event's event_id, since
    this event vocabulary has no cancel/expire counterpart for context.

    There is no separate staleness/version field: event_count already is
    one (Rule: "Only include fields supported by the repository" --
    adding a second field purely to duplicate what event_count already
    tells a caller would not be a new, useful field). get() is a plain
    store read with no staleness check of its own (see
    LLMAgentTaskEventProjectionService.get()'s own docstring for why) --
    a caller who wants a fresh view compares this field against
    LLMAgentTaskEventQueryService.count(task_id), or simply calls
    refresh() again.
    """

    task_id: str
    current_state: str
    last_event_id: Optional[str]
    last_event_at: Optional[datetime]
    event_count: int
    last_error_reference: Optional[str]
    active_retry_reference: Optional[str]
    active_context_reference: Optional[str]
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["evaluated_at"] = self.evaluated_at.isoformat()
        if isinstance(self.last_event_at, datetime):
            data["last_event_at"] = self.last_event_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskEventProjection":
        payload = dict(data)
        for key in ("evaluated_at", "last_event_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)


# The AgentTaskEventProjection fields LLMAgentTaskEventProjectionReconciliationService
# actually compares -- deliberately excludes task_id (always equal by
# construction: both sides are built for the same task_id) and evaluated_at
# (pure bookkeeping: every fresh project() call gets a new one regardless of
# whether anything about the task actually changed, the same "content is
# stable, only the store's own bookkeeping timestamp moves" convention
# backend.agent_task_readiness_projection's own projection_id/evaluated_at
# already establishes -- comparing it would make is_current never true).
PROJECTION_COMPARISON_FIELDS = (
    "current_state",
    "last_event_id",
    "last_event_at",
    "event_count",
    "last_error_reference",
    "active_retry_reference",
    "active_context_reference",
)


@dataclass(frozen=True)
class AgentTaskProjectionDifference:
    """One field where a stored AgentTaskEventProjection disagreed with a
    freshly event-derived one -- field is one of
    PROJECTION_COMPARISON_FIELDS, or the literal "projection" when there
    was no stored projection to compare at all (Rule: "Do not silently
    discard projection differences" -- a missing projection is itself a
    reportable difference, not a special case that produces an empty
    differences list).
    """

    field: str
    stored: object
    expected: object


@dataclass(frozen=True)
class AgentTaskProjectionReconciliationResult:
    """LLMAgentTaskEventProjectionReconciliationService.check()/
    reconcile()'s complete, structured outcome for one task_id.

    is_current is exactly `not differences`, computed once by check() and
    carried unchanged into reconcile()'s own returned result even after a
    fix was applied (Rule: "Do not silently discard projection
    differences") -- it always answers "was the stored projection current
    *before* this call took any action," never "is it current now."
    reconciled is the separate flag for whether an action was actually
    taken: always False from check() (Rule: "check() is strictly
    read-only"), and True from reconcile() exactly when persistence
    happened.

    stored_projection/expected_projection are Commit #7's own
    AgentTaskEventProjection, embedded directly -- never re-derived or
    reshaped a second time here (Rule: "Reuse ... Commit #7 projection
    logic").
    """

    task_id: str
    is_current: bool
    stored_projection: Optional[AgentTaskEventProjection]
    expected_projection: AgentTaskEventProjection
    differences: tuple
    reconciled: bool
