from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Plain string outcome vocabulary, the same convention as every other
# status/finding-code enum in this series (Commits #9-12).
NOOP_FRESH = "noop_fresh"
PLANNING_FAILED = "planning_failed"
REFRESH_FAILED = "refresh_failed"
VALIDATION_FAILED = "validation_failed"
ACTIVATED = "activated"

DECISION_OUTCOMES = (
    NOOP_FRESH,
    PLANNING_FAILED,
    REFRESH_FAILED,
    VALIDATION_FAILED,
    ACTIVATED,
)


@dataclass(frozen=True)
class LLMContextRefreshDecision:
    """The single deterministic outcome of one orchestrated refresh() call.

    No existing Commit #1-#12 record represents this: LLMContextRefreshPlan
    (Commit #10), LLMContextRefreshExecution (Commit #11), and
    LLMContextRefreshValidation (Commit #12) each describe one stage, and a
    NOOP_FRESH or PLANNING_FAILED outcome may have no execution or
    validation at all. plan_id/execution_id/validation_id are None for
    whichever stages the workflow never reached.
    """

    context_id: str
    outcome: str
    reason: str
    plan_id: Optional[str] = None
    execution_id: Optional[str] = None
    validation_id: Optional[str] = None
    decision_id: str = field(default_factory=lambda: str(uuid4()))
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
