from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.llm.context_provenance import LLMContextProvenance


def _provenance_to_dict(record: LLMContextProvenance) -> dict:
    data = asdict(record)
    if isinstance(data.get("created_at"), datetime):
        data["created_at"] = data["created_at"].isoformat()
    return data


def _provenance_from_dict(data: dict) -> LLMContextProvenance:
    payload = dict(data)
    created_at = payload.get("created_at")
    if isinstance(created_at, str):
        payload["created_at"] = datetime.fromisoformat(created_at)
    return LLMContextProvenance(**payload)


@dataclass(frozen=True)
class TaskContextSnapshot:
    """An immutable, point-in-time record of the exact resolved context a
    task had at creation time -- enough for an agent execution to
    reproduce exactly what context it saw, later.

    Unlike Commit #1's own LLMAgentTaskContextSnapshot (a copy of the
    task's own stored fields -- objective/constraints/inputs/
    relevant_context/provenance, as they stood in the task record
    itself), resolved_context here is Commit #2's own *resolved* view:
    {"context": [...], "memories": [...]} -- selected_context and
    selected_memories from a fresh LLMAgentTaskContextResolver.resolve()
    call, capturing supplemental project context and agent memory the
    task's own stored record never holds. provenance is that same
    resolution's own provenance trail, embedded verbatim (Rule:
    "preserve complete provenance").

    context_version is this service's own per-task monotonic counter --
    1, then 2, then 3... -- computed the exact same way backend.llm.
    context_version.LLMContextVersionService.snapshot() already computes
    a project context's own version (next = previous + 1, 1 if none),
    the established pattern reused here rather than that service itself
    (which snapshots a single LLMProjectContext's own content -- a
    mismatched domain for a task's composite resolved context, the same
    reasoning Commit #7 already used to reuse Commit #1's own snapshot()
    instead of LLMContextVersionService for a materially identical
    reason).
    """

    task_id: str
    scope_id: str
    context_version: int
    resolved_context: dict
    provenance: tuple
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "scope_id": self.scope_id,
            "context_version": self.context_version,
            "resolved_context": self.resolved_context,
            "provenance": [_provenance_to_dict(record) for record in self.provenance],
            "snapshot_id": self.snapshot_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskContextSnapshot":
        payload = dict(data)
        payload["provenance"] = tuple(_provenance_from_dict(record) for record in payload.get("provenance", []))
        created_at = payload.get("created_at")
        if isinstance(created_at, str):
            payload["created_at"] = datetime.fromisoformat(created_at)
        return cls(**payload)
