from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from uuid import uuid4

from backend.llm.context_provenance import LLMContextProvenance

# Default budget select_relevant_context() uses when a caller does not name
# one -- same "a sensible default, not a caller-mandatory argument" shape as
# backend.llm.tool_results.DEFAULT_OUTPUT_TOKEN_BUDGET.
DEFAULT_TASK_CONTEXT_TOKEN_BUDGET = 4000


def _provenance_to_dict(entry) -> dict:
    data = asdict(entry) if isinstance(entry, LLMContextProvenance) else dict(entry)
    if isinstance(data.get("created_at"), datetime):
        data["created_at"] = data["created_at"].isoformat()
    return data


def _provenance_from_dict(data: dict) -> LLMContextProvenance:
    if isinstance(data, LLMContextProvenance):
        return data
    payload = dict(data)
    created_at = payload.get("created_at")
    if isinstance(created_at, str):
        payload["created_at"] = datetime.fromisoformat(created_at)
    elif created_at is None:
        payload["created_at"] = datetime.now(timezone.utc)
    payload.setdefault("provenance_id", str(uuid4()))
    return LLMContextProvenance(**payload)


@dataclass
class LLMAgentTaskContext:
    """The canonical, structured representation of one task an agent is
    working, scoped to (task_id, agent_id, scope_id).

    Not a second project-context or memory store: relevant_context holds
    the already-selected/compacted slice of context relevant to this task
    (built by backend.llm.context_selection/backend.llm.context_compaction
    -- see LLMAgentTaskContextService.select_relevant_context()), and
    provenance is an append-only trail of backend.llm.context_provenance.
    LLMContextProvenance records explaining where each entry came from --
    the exact same provenance primitive already used to trace stored LLM
    context, reused here rather than a second provenance shape. Nothing
    here executes or plans a task; this is inert, structured input for
    whatever does.
    """

    agent_id: str
    scope_id: str
    objective: str
    constraints: list = field(default_factory=list)
    inputs: dict = field(default_factory=dict)
    relevant_context: list = field(default_factory=list)
    provenance: list = field(default_factory=list)
    task_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["provenance"] = [_provenance_to_dict(entry) for entry in self.provenance]
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentTaskContext":
        payload = dict(data)
        payload["provenance"] = [_provenance_from_dict(entry) for entry in payload.get("provenance", [])]
        for key in ("created_at", "updated_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)


@dataclass(frozen=True)
class LLMAgentTaskContextSnapshot:
    """An immutable, point-in-time copy of one LLMAgentTaskContext.

    Taken by LLMAgentTaskContextService.snapshot(): every field is copied
    at the moment of the call, so a later update() to the live task
    context can never change a snapshot already handed to a caller. List
    fields are tuples (structurally immutable, unlike the live record's
    own plain lists) and this class is itself a frozen dataclass, so
    reassigning any field raises dataclasses.FrozenInstanceError.
    """

    task_id: str
    agent_id: str
    scope_id: str
    objective: str
    constraints: tuple
    inputs: MappingProxyType
    relevant_context: tuple
    provenance: tuple
    created_at: datetime
    updated_at: datetime
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    snapshotted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
