from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# The kinds of durable context a project/notebook/API scope can hold.
# Deliberately small and closed: an open-ended type would make list()
# filtering and downstream prompt assembly unpredictable.
VALID_CONTEXT_TYPES = frozenset(
    {
        "system_prompt",
        "instruction",
        "summary",
        "fact",
        "preference",
    }
)


@dataclass
class LLMProjectContext:
    """Durable context scoped to a project/notebook/API identifier.

    Unlike backend.llm.context.LLMContext -- assembled fresh for a single
    LLM call and discarded with it -- an LLMProjectContext is written once
    and read back across many notebook/API workflows that share the same
    scope_id.
    """

    scope_id: str
    context_type: str
    content: Any
    context_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMProjectContext":
        payload = dict(data)
        for key in ("created_at", "updated_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)
