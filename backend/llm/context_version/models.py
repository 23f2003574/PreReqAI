from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class LLMContextVersion:
    """An immutable, point-in-time snapshot of one LLMProjectContext's content.

    Unlike LLMProjectContext (Commit #1), which is mutated in place by
    update(), a version is never changed once created -- it is the
    reproducible record of what a context's content was at version N.
    """

    context_id: str
    version: int
    content: Any
    version_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMContextVersion":
        payload = dict(data)
        value = payload.get("created_at")
        if isinstance(value, str):
            payload["created_at"] = datetime.fromisoformat(value)
        return cls(**payload)
