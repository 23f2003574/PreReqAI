from dataclasses import dataclass, field
from typing import Any, Optional

from backend.agent_policy_risk_assessment import RiskAssessment
from backend.agent_policy_risk_classification import RiskClassification
from backend.agent_policy_risk_decision import RiskDecision
from backend.agent_policy_risk_review_queue import ReviewItem


@dataclass(frozen=True)
class RiskGovernanceResult(object):
    """LLMAgentRiskGovernanceOrchestrator.evaluate()'s complete, one-shot
    governance verdict for one agent action -- the final composition of
    Commits #1-#12, never a second computation of anything any of them
    already does.

    final_decision is Commit #1's own ALLOW/DENY plus Commit #3's own
    REVIEW -- the same three-value vocabulary this whole series has used
    since Commit #4, extended here with what "review" actually resolves
    to once Commit #8's own review queue (and, transitively, Commits
    #5/#6/#9/#10) have had a chance to already settle it: ALLOW once a
    review item is RESOLVED as APPROVED, DENY once it is RESOLVED as
    REJECTED or has lapsed to EXPIRED, and REVIEW itself only while a
    review item is still genuinely PENDING/CLAIMED, awaiting a human.

    assessment/classification/decision/review_item are each embedded
    verbatim -- Commit #1's RiskAssessment, Commit #2's
    RiskClassification, Commit #4's RiskDecision, and (when a REVIEW
    decision was actually enqueued) Commit #8's own ReviewItem -- the
    same "embed a prior commit's full result, never re-summarize"
    convention this series has kept since Commit #2 (see Rules:
    "Preserve every decision and provenance record").

    executed is the real backend.agent_step_execution.LLMAgentStepExecution
    this evaluate() call actually produced by delegating to an injected
    execution_service once final_decision resolved to ALLOW -- None
    whenever no execution_service was configured, or final_decision is
    not ALLOW (a DENY or still-pending REVIEW never executes anything;
    see Rules: "review cannot execute without valid approval").

    Deliberately carries no timestamp of its own -- every timestamp
    that matters (assessment/decision/review_item's own created_at/
    resolved_at/expires_at) is already preserved inside the embedded
    objects, the same determinism discipline every prior result type in
    this series already established.
    """

    final_decision: str
    scope_id: Optional[str]
    assessment: RiskAssessment
    classification: RiskClassification
    decision: RiskDecision
    review_item: Optional[ReviewItem]
    executed: Optional[Any]
    reasons: list
    provenance: dict = field(default_factory=dict)
