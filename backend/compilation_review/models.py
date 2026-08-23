from dataclasses import dataclass
from datetime import datetime


APPROVED = "APPROVED"
REJECTED = "REJECTED"
STATUSES = frozenset({APPROVED, REJECTED})


@dataclass(frozen=True)
class LLMCompilationReview:
    """The outcome of reviewing one LLMCompilationPlan before compiler execution.

    findings is a list of {"category", "target", "message", "blocking"}
    dicts -- status is APPROVED only when none of them are blocking. This
    record is the review's own result; producing it never changes the plan,
    or anything upstream of it.
    """

    review_id: str
    plan_id: str
    status: str
    findings: list
    reviewed_at: datetime
