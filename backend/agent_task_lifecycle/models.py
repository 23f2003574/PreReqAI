from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# This module's own lifecycle vocabulary. No repository-wide "task status"
# enum already exists to reuse: backend.agent_task_context's
# LLMAgentTaskContext carries no status field at all (it is inert,
# structured input -- see that module's own models.py), and
# backend.agent_task_planning's READY/REJECTED describes one LLMAgentPlan's
# own validity, not a task's progress through execution. Lowercase values,
# the same convention backend.agent_policy_history.CHANGE_TYPES and
# backend.agent_risk_profile_rollout.STATES already use for a closed,
# human-readable status vocabulary (as opposed to the UPPERCASE convention
# backend.llm.tool_execution/backend.agent_capability_execution use for
# their own, unrelated, outcome vocabularies).
CREATED = "created"
PLANNED = "planned"
READY = "ready"
RUNNING = "running"
PAUSED = "paused"
CANCELLED = "cancelled"
FAILED = "failed"
COMPLETED = "completed"
STATES = frozenset({CREATED, PLANNED, READY, RUNNING, PAUSED, CANCELLED, FAILED, COMPLETED})

# A task is done, one way or another, once it reaches one of these --
# LLMAgentTaskLifecycleService.can_transition() never reports an edge out
# of any of them (self-transitions aside -- see TRANSITIONS' own docstring
# below), the same "terminal means terminal" discipline
# backend.llm.tool_execution.TERMINAL_STATUSES already establishes for its
# own, unrelated, execution-outcome vocabulary.
TERMINAL_STATES = frozenset({COMPLETED, FAILED, CANCELLED})

# The lifecycle graph this goal's own diagram describes, plus the minimal
# extra edges that same diagram implies rather than invents:
#   - CREATED/PLANNED/READY may each be CANCELLED directly -- a task can be
#     abandoned before it ever runs, not only once RUNNING.
#   - PLANNED and READY may each fail outright (e.g. planning itself turns
#     out unviable, or a readiness check fails) -- the diagram's own
#     "ready → running ↘ failed" branch, read as "the step before running
#     can itself fail" rather than as an edge only reachable from RUNNING.
#   - PAUSED may resume to RUNNING, or end in CANCELLED/FAILED -- the
#     mirror image of RUNNING's own "paused/cancelled/failed" branch: a
#     pause is a suspension of a still-live task, not a side state with no
#     way back in.
# Every state not listed as a key here is terminal (see TERMINAL_STATES)
# and maps to frozenset() -- no outgoing edges at all.
TRANSITIONS: dict[str, frozenset[str]] = {
    CREATED: frozenset({PLANNED, CANCELLED}),
    PLANNED: frozenset({READY, FAILED, CANCELLED}),
    READY: frozenset({RUNNING, FAILED, CANCELLED}),
    RUNNING: frozenset({COMPLETED, FAILED, PAUSED, CANCELLED}),
    PAUSED: frozenset({RUNNING, FAILED, CANCELLED}),
}


class InvalidAgentTaskError(ValueError):
    """Raised when create()'s task_definition, or an explicitly given
    task_id, fails validation."""


class UnknownAgentTaskError(KeyError):
    """Raised when get()/transition()/history() is given a task_id that
    was never created."""


class InvalidTaskTransitionError(ValueError):
    """Raised when transition() is given a target_state that is not one
    of STATES, or that can_transition() reports as not reachable from the
    task's own current_state."""


@dataclass
class AgentTask:
    """The canonical lifecycle record for one task an agent is working,
    scoped to (task_id, agent_id, scope_id).

    Not a second task-context store: this record owns only lifecycle
    state (current_state/previous_state/transition_reason) plus the bare
    identity/definition a caller supplied at create() time. Whatever a
    task actually needs to execute -- objective, constraints, relevant
    context -- already has a canonical home in
    backend.agent_task_context.LLMAgentTaskContext; definition here is
    deliberately just an opaque, caller-supplied dict (never interpreted
    or validated beyond "is it a dict") so this service never grows a
    second, competing notion of what a task's own working data looks
    like.

    previous_state/transition_reason describe only the most recent
    transition; a task's complete transition trail is a separate,
    append-only TaskTransitionRecord history (see
    LLMAgentTaskLifecycleService.history()) -- the same
    "current-state-plus-full-append-only-trail" split
    backend.agent_policy_history/backend.agent_risk_profile_history
    already use for their own entities, kept local here rather than
    reusing either of those (both are already bound to their own,
    unrelated entity shapes).
    """

    agent_id: str
    scope_id: str
    objective: str
    definition: dict = field(default_factory=dict)
    current_state: str = CREATED
    previous_state: Optional[str] = None
    transition_reason: Optional[str] = None
    task_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTask":
        payload = dict(data)
        for key in ("created_at", "updated_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class TaskTransitionRecord:
    """One immutable, append-only entry in a task's own transition
    history, written by every successful LLMAgentTaskLifecycleService.
    transition() call (create() writes the first one itself, from_state
    None, to_state CREATED -- the same "before is None only for the
    creation event" convention
    backend.agent_policy_history.LLMAgentPolicyChange already
    establishes).

    Never updated or deleted once recorded -- the same append-only
    discipline backend.agent_strategy_lifecycle.
    LLMAgentStrategyLifecycleDecision and backend.agent_policy_history.
    LLMAgentPolicyChange already establish elsewhere in this repository.
    An idempotent self-transition (target_state == current current_state)
    never appends a record here -- see LLMAgentTaskLifecycleService.
    transition()'s own docstring.
    """

    task_id: str
    from_state: Optional[str]
    to_state: str
    reason: Optional[str] = None
    transition_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["occurred_at"] = self.occurred_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TaskTransitionRecord":
        payload = dict(data)
        value = payload.get("occurred_at")
        if isinstance(value, str):
            payload["occurred_at"] = datetime.fromisoformat(value)
        return cls(**payload)
