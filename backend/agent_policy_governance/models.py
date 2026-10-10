from dataclasses import dataclass
from typing import Optional

from backend.agent_policy_audit import LLMAgentPolicyDecisionAudit
from backend.agent_policy_decision import PolicyDecision


@dataclass(frozen=True)
class GovernanceResult:
    """evaluate_action()'s complete, provenance-preserving outcome for
    one action -- the single object that "exposes result/provenance"
    per this commit's own flow.

    decision is exactly the Commit #3-#5 PolicyDecision
    LLMAgentPolicyEnforcement.enforce() produced -- full rule/exception
    provenance, unmodified. blocked is Commit #4's own is_blocking(decision)
    -- what would actually happen at the real execution boundary, kept
    distinct from decision.decision for the exact reason Commit #4/#6
    already established: a bare default-deny (nothing configured) is not
    a block. audit is the Commit #7 LLMAgentPolicyDecisionAudit this
    evaluation recorded, or None when no execution_or_action_id was
    available to record one against, or the audit store itself failed
    (see LLMAgentPolicyGovernanceOrchestrator: "audit failure never
    changes the governance result") -- its absence never implies the
    decision itself is any less real or any less enforced.
    """

    action_context: dict
    scope_id: Optional[str]
    execution_or_action_id: Optional[str]
    decision: PolicyDecision
    blocked: bool
    audit: Optional[LLMAgentPolicyDecisionAudit]
