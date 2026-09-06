from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from backend.agent_policy_risk_decision import RiskDecision


@dataclass(frozen=True)
class ReviewResolution(object):
    """LLMAgentRiskReviewResolver.resolve()'s complete, provenance-
    preserving outcome for one Commit #8 ReviewItem.

    Not a second resolution record: every field here is read straight
    off the Commit #8 ReviewItem that Commit #5's own approve()/
    reject() (or Commit #6's own resolve(), driven through by Commit
    #8's own complete()) already durably updated -- this is a read-only
    reshaping for the caller of resolve(), never a parallel source of
    truth. decision is the original Commit #4 RiskDecision, preserved
    verbatim (see Rules: "Preserve reviewer, reason, risk evidence, and
    provenance").

    Attributes:
        item_id: The Commit #8 ReviewItem.item_id this resolution is for
        scope_id: The scope this resolution belongs to
        outcome: APPROVED or REJECTED (Commit #5's own constants, reused
            as-is)
        reviewer: Who resolved this item
        reason: Why, required for REJECTED, optional for APPROVED
        decision: The original Commit #4 RiskDecision, preserved
            verbatim
        approval_request_id: The Commit #5 ApprovalRequirement.request_id
            this resolution drove
        escalation_id: The Commit #6 Escalation.escalation_id this
            resolution was driven through, or None if it was resolved
            directly against the approval gate
        resolved_at: When this resolution was recorded
        provenance: {item_id, review_item, decision}, embedding the full
            Commit #8 ReviewItem verbatim -- the same "embed a prior
            commit's full result, never re-summarize" convention this
            series has kept since Commit #2
    """

    item_id: str
    scope_id: str
    outcome: str
    reviewer: str
    reason: Optional[str]
    decision: RiskDecision
    approval_request_id: str
    escalation_id: Optional[str]
    resolved_at: datetime
    provenance: dict = field(default_factory=dict)
