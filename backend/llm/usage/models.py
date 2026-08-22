from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMUsageRecord:
    """An immutable, normalized record of token consumption for one request."""

    usage_id: str
    request_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    recorded_at: datetime
