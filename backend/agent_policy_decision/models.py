from dataclasses import dataclass, field

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

    exceptions_applied is empty for every PolicyDecision this module's
    own LLMAgentPolicyDecisionEngine.decide() produces -- it never grants
    an exception, and has no notion that one could exist. It exists only
    so a later, optional layer
    (backend.agent_policy_exceptions.LLMAgentPolicyExceptionAwareDecisionEngine)
    can report, on the exact same PolicyDecision shape, which Commit #5
    LLMAgentPolicyException records (if any) turned what would otherwise
    have been a DENY into this ALLOW -- without that layer needing a
    second, differently-shaped decision type, and without this decide()
    or LLMAgentPolicyEvaluator ever having to know exceptions exist.
    """

    decision: str
    matched_rules: list
    reasons: list
    provenance: list
    exceptions_applied: list = field(default_factory=list)
