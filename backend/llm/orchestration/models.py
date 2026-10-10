from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class LLMRequestDecision:
    """The single, deterministic outcome of orchestrating one LLM request."""

    decision_id: str
    request_id: str
    provider: Optional[str]
    model: Optional[str]
    cached: bool
    allowed: bool
    reason: str
    created_at: datetime
