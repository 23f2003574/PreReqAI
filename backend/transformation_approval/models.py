from dataclasses import dataclass
from datetime import datetime
from typing import Optional

PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
STATUSES = frozenset({PENDING, APPROVED, REJECTED})


@dataclass(frozen=True)
class LLMTransformationApproval:
    """One reviewer's immutable decision on a validated LLMTransformationDiff.

    status is always APPROVED or REJECTED -- a diff with no recorded
    approval is implicitly PENDING (see LLMTransformationApprovalService.
    status()). reason is required for a REJECTED decision and always None
    for an APPROVED one. Once created, a decision can never be revised or
    replaced for the same diff_id -- see
    LLMTransformationApprovalService.approve()/reject().
    """

    approval_id: str
    diff_id: str
    reviewer: str
    status: str
    reason: Optional[str]
    approved_at: datetime
