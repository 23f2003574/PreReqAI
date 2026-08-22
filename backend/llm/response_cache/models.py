from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..models import LLMResponse


@dataclass(frozen=True)
class LLMCacheEntry:
    """An immutable cached LLMResponse for one deterministic request.

    `cache_key` combines model + request_hash (the rule that the key must
    include the model plus relevant request context); `request_hash` is the
    hash of just the request content, independent of model.
    """

    cache_key: str
    request_hash: str
    response: LLMResponse
    model: str
    expires_at: Optional[datetime]
    created_at: datetime
