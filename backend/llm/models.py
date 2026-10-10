from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMRequest:
    """Provider-neutral request payload for an LLM completion."""

    model: str
    messages: list
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    def validate(self):
        if not self.model or not isinstance(self.model, str):
            raise ValueError("LLMRequest.model must be a non-empty string")

        if not self.messages:
            raise ValueError("LLMRequest.messages must not be empty")

        for message in self.messages:
            if "role" not in message or "content" not in message:
                raise ValueError(
                    "each message must have a 'role' and 'content' key"
                )

        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError("LLMRequest.temperature must be between 0.0 and 2.0")

        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("LLMRequest.max_tokens must be a positive integer")


@dataclass
class LLMResponse:
    """Provider-neutral, normalized response from an LLM completion."""

    content: str
    model: str
    usage: dict = field(default_factory=dict)
    finish_reason: str = "stop"
