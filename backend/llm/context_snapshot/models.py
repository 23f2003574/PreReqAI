from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


@dataclass(frozen=True)
class LLMContextSnapshot:
    """An immutable record of the exact context injected into one LLM request.

    Captures Commit #7's inject() output, not Commit #3's raw retrieval
    candidates: context_items is exactly the CONTEXT_ROLE messages that made
    it into the request that was actually sent, in the order they were
    injected, each carrying its Commit #6 provenance when it has any.
    """

    request_id: str
    scope_id: Optional[str]
    context_items: tuple
    token_count: int
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """The project's dataclass -> json.dumps(sort_keys=True) convention."""
        return {
            "snapshot_id": self.snapshot_id,
            "request_id": self.request_id,
            "scope_id": self.scope_id,
            "context_items": [dict(item) for item in self.context_items],
            "token_count": self.token_count,
            "created_at": self.created_at.isoformat(),
        }
