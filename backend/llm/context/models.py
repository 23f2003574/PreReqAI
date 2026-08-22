from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMContextItem:
    """A single unit of context content that may be included in a request."""

    type: str
    content: str
    priority: int = 0
    id: Optional[str] = None

    def validate(self):
        if not self.type or not isinstance(self.type, str):
            raise ValueError("LLMContextItem.type is required")

        if not self.content or not isinstance(self.content, str):
            raise ValueError("LLMContextItem.content is required")

        if not isinstance(self.priority, int):
            raise ValueError("LLMContextItem.priority must be an integer")


@dataclass
class LLMContext:
    """Structured, per-request context assembled for an LLM call."""

    request_id: str
    system: Optional[str] = None
    messages: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    token_budget: Optional[int] = None
