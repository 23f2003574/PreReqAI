from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class LLMRequestAudit:
    """An immutable snapshot of an LLM request's lifecycle at one point in time.

    LLMRequestAuditService never mutates an existing snapshot -- each
    lifecycle event (start, a fallback attempt, completion) appends a new
    snapshot to that request's append-only trail.
    """

    audit_id: str
    request_id: str
    provider: str
    model: str
    status: str
    attempts: int
    total_tokens: int
    total_cost: float
    created_at: datetime
    completed_at: Optional[datetime]
