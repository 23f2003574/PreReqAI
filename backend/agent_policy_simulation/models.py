from dataclasses import dataclass
from datetime import datetime

from backend.agent_policy_decision import PolicyDecision
from backend.agent_policy_engine import LLMAgentPolicyDecision


@dataclass(frozen=True)
class PolicyConflict:
    """One pair of resolved policies that reached opposite explicit
    verdicts for the same simulated action.

    Pure reporting: Commit #3's own decide() has already
    deterministically resolved every such conflict (an explicit deny
    always wins), so detecting one here never changes
    PolicySimulationResult.final_decision -- it only makes visible *why*
    the verdict was what it was, per Commit #6's own "surface conflicts
    rather than hiding them" rule, instead of a caller only ever seeing
    the single decision that survived.
    """

    allow: LLMAgentPolicyDecision
    deny: LLMAgentPolicyDecision


@dataclass(frozen=True)
class PolicySimulationResult:
    """simulate()'s complete, read-only preview of what
    LLMAgentPolicyEnforcement.enforce() would decide for one
    action_context -- and, separately, what that would mean at the real
    execution boundary -- without ever calling enforce() a second time,
    reaching an execution boundary, or mutating anything.

    final_decision is exactly the PolicyDecision enforce() itself
    returned for this action_context -- never recomputed or
    reinterpreted, so simulation and a genuine enforcement call can never
    disagree (Commit #6's own "simulation/enforcement decision parity"
    rule). matched_policies/matched_rules/applicable_exceptions/reasons/
    provenance surface that same PolicyDecision's own data under
    simulation-facing names.

    would_allow is deliberately a *different* question from
    final_decision.decision == ALLOW: it is
    backend.agent_policy_enforcement.is_blocking() applied to
    final_decision, the exact same predicate
    LLMAgentPolicyEnforcedExecutionService's real execution boundary
    already uses to decide whether to actually stop an action -- so
    would_allow is what would truly happen at that boundary (a bare
    default-deny with nothing explicit behind it still lets the action
    through, exactly Commit #4's own backward-compatibility rule),
    while final_decision.decision is the raw policy verdict on its own,
    the way an actual, already-recorded enforcement decision would read.
    Keeping both distinct is this class's whole purpose: "clearly
    distinguish what would be allowed/denied from an actual enforcement
    decision."

    conflicts additionally lists every pair of resolved policies that
    disagreed (one explicit ALLOW, one explicit DENY) for this action --
    see PolicyConflict.
    """

    action_context: dict
    would_allow: bool
    final_decision: PolicyDecision
    matched_policies: list
    matched_rules: list
    applicable_exceptions: list
    conflicts: list
    reasons: list
    provenance: list
    simulated_at: datetime
