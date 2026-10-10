from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Plain string status vocabulary, the same convention as
# backend.llm.tool_execution's STATUSES and backend.llm.context_refresh's
# ACTIONABLE/UNRESOLVABLE.
SUCCEEDED = "succeeded"
PARTIAL = "partial"
FAILED = "failed"
ROLLED_BACK = "rolled_back"

EXECUTION_STATUSES = (SUCCEEDED, PARTIAL, FAILED, ROLLED_BACK)


@dataclass(frozen=True)
class LLMContextRefreshExecution:
    """The outcome of applying a Commit #10 refresh plan.

    refreshed_context_ids lists every context that was actually updated --
    empty when every action failed. status distinguishes a plan whose
    actions all applied (SUCCEEDED), one where only some did
    (PARTIAL -- the rest left the existing context exactly as it was),
    one where none did (FAILED), and one that has since been rolled back
    (ROLLED_BACK).
    """

    plan_id: str
    status: str
    refreshed_context_ids: tuple
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
