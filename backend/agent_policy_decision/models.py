from dataclasses import dataclass

from backend.agent_policy_engine import LLMAgentPolicyDecision
from backend.agent_policy_resolution import ResolvedPolicy


@dataclass(frozen=True)
class PolicyEvaluationTrace:
    """One Commit #2 ResolvedPolicy together with the Commit #1
    LLMAgentPolicyEvaluator decision it produced for one action -- one
    entry per policy the decision engine actually evaluated, whether or
    not any of its rules matched.

    This is the complete audit trail decide() builds: every policy that
    was considered stays reachable here, with its own precedence/source
    (from ResolvedPolicy) and its own allow/deny verdict, rule_id, and
    reason (from LLMAgentPolicyDecision) -- nothing evaluated is ever
    silently dropped, even a policy whose verdict did not end up
    determining the final PolicyDecision.
    """

    resolved: ResolvedPolicy
    decision: LLMAgentPolicyDecision


@dataclass(frozen=True)
class PolicyDecision:
    """decide()'s complete, provenance-preserving outcome for one action
    against a whole resolved set of Commit #1 policies.

    decision is the final ALLOW/DENY verdict (Commit #1's own
    vocabulary, reused as-is). matched_rules is every
    LLMAgentPolicyDecision that actually determined this verdict --
    every explicit DENY found (when decision is DENY: "any explicit deny
    blocks the action", so every one of them is responsible) or, absent
    any deny, every explicit ALLOW found (when decision is ALLOW); a
    verdict reached because nothing applied at all (no policy, or no
    rule in any resolved policy matched) leaves matched_rules empty.
    reasons is the same set of decisions' own reason strings, in the same
    order. provenance is the complete audit trail (see
    PolicyEvaluationTrace) -- every resolved policy this decide() call
    actually evaluated, in the exact order it was evaluated, whether or
    not it contributed to matched_rules -- so a decision is never merely
    implied by matched_rules alone.
    """

    decision: str
    matched_rules: list
    reasons: list
    provenance: list
