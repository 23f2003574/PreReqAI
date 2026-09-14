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
