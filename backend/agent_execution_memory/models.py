from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.llm.tool_execution import FAILED, SUCCEEDED

# The kinds of reusable execution knowledge a scope can accumulate.
# Deliberately small and closed, the same reasoning
# backend.llm.project_context.VALID_CONTEXT_TYPES documents: an open-ended
# type would make list() filtering and downstream reuse unpredictable.
VALID_MEMORY_TYPES = frozenset(
    {
        "strategy",
        "tool_usage",
        "failure_pattern",
        "heuristic",
    }
)

# outcome is never taken on the caller's word -- record() derives it from
# the originating execution's own verified terminal status (Commit #12's
# LLMAgentPlanExecutionService), so only these two ever reach storage.
VALID_OUTCOMES = frozenset({SUCCEEDED, FAILED})


@dataclass
class LLMAgentMemory:
    """One durable, reusable outcome distilled from a completed agent execution.

    Unlike backend.llm.context.LLMContext -- assembled fresh for a single
    LLM call and discarded with it -- and unlike
    backend.llm.project_context.LLMProjectContext -- durable context a
    caller writes and updates directly -- an LLMAgentMemory is never
    written by hand: it is only ever produced by
    LLMAgentMemoryService.record() from a specific, already-finished
    execution_id, and outcome always reflects that execution's own
    verified status rather than anything the caller claims.
    """

    scope_id: str
    execution_id: str
    memory_type: str
    content: Any
    outcome: str
    memory_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentMemory":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
