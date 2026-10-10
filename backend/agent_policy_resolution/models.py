from dataclasses import dataclass

from backend.agent_policy_engine import LLMAgentPolicy


@dataclass(frozen=True)
class ResolvedPolicy:
    """One Commit #1 LLMAgentPolicy as resolved for a specific scope,
    ranked against every other policy resolved alongside it.

    A pure record of the resolver's own decision, the same value-object
    discipline backend.agent_policy_engine.LLMAgentPolicyDecision already
    keeps for an evaluation decision: ResolvedPolicy performs no ordering
    of its own. precedence is the resolved rank, lowest first (0 is
    highest precedence -- the first a caller should hand to
    LLMAgentPolicyEvaluator.evaluate() when only one decision is wanted);
    source is a human-readable account of where this ranking came from,
    so two policies' relative order is always explainable, never merely
    implied by list position.
    """

    policy: LLMAgentPolicy
    precedence: int
    source: str
