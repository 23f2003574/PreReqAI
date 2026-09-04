from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyEvaluator
from backend.agent_policy_resolution import ResolvedPolicy

from .models import PolicyDecision, PolicyEvaluationTrace

_DEFAULT_DENY_REASON_WITH_POLICIES = (
    "no policy rule matched this action across the resolved policies; denied by default"
)
_DEFAULT_DENY_REASON_NO_POLICIES = "no policy applies to this action; denied by default"


class InvalidPolicyDecisionInputError(ValueError):
    """Raised when decide() is given an action_context that is not a
    dict, or resolved_policies that is not a list of ResolvedPolicy."""


class LLMAgentPolicyDecisionEngine:
    """Evaluates a complete agent action against a whole Commit #2
    resolved policy set and produces one authoritative, deterministic
    allow/deny PolicyDecision.

    Not a second evaluation framework: every actual rule-matching
    decision is Commit #1's own LLMAgentPolicyEvaluator.evaluate(),
    called once per Commit #2 ResolvedPolicy and never reimplemented
    here. This engine adds only what neither Commit #1 nor Commit #2 has
    any notion of -- aggregating *many* policies' individual verdicts
    into one action-level decision:

    - every resolved policy is evaluated, in its given (precedence)
      order, before any verdict is reached -- "evaluate all applicable
      policies" is never short-circuited, so a lower-precedence policy's
      explicit deny is never missed just because an earlier policy
      already allowed
    - any explicit deny -- a rule that actually matched, with effect
      DENY -- blocks the action outright, exactly the "explicit deny
      always wins" convention Commit #1's own evaluator already applies
      within a single policy, extended here across every policy in the
      resolved set
    - absent any explicit deny, any explicit allow (a matched ALLOW rule)
      allows the action
    - a policy that produced a verdict without any of its own rules
      matching (Commit #1's own per-policy default-deny, or an archived
      policy's unconditional deny) contributes nothing to either
      count -- it is not a rule "explicitly" denying or allowing
      anything, so it can never single-handedly override an explicit
      verdict elsewhere in the set
    - no policy at all, or no rule anywhere in the resolved set matching,
      follows the exact same repository default
      backend.llm.tool_permissions.LLMToolPermissionService.authorize()
      and Commit #1's own LLMAgentPolicyEvaluator already use: deny by
      default

    decide() never mutates a policy, a ResolvedPolicy, or the
    action_context, and never calls anything beyond
    LLMAgentPolicyEvaluator.evaluate() -- it is pure, side-effect-free
    aggregation, so the same (action_context, resolved_policies) pair
    always reaches the same PolicyDecision. No LLM call is made anywhere
    in this evaluation.
    """

    def __init__(self, evaluator: LLMAgentPolicyEvaluator = None):
        self._evaluator = evaluator or LLMAgentPolicyEvaluator()

    def decide(self, action_context: dict, resolved_policies: list) -> PolicyDecision:
        """Decide whether `action_context` is allowed under every policy
        in `resolved_policies`.

        resolved_policies is normally exactly what Commit #2's
        LLMAgentPolicyResolver.resolve()/resolve_for_execution() returned
        -- a list of ResolvedPolicy, already scope-isolated and
        precedence-ordered -- but decide() itself trusts nothing about
        that beyond each entry actually being a ResolvedPolicy; it never
        re-resolves or re-orders anything on its own.

        Raises:
            InvalidPolicyDecisionInputError: If action_context is not a
                dict, or resolved_policies is not a list of ResolvedPolicy
            InvalidPolicyEvaluationError: Propagated from
                LLMAgentPolicyEvaluator.evaluate() if a resolved policy's
                own policy is invalid
        """
        if not isinstance(action_context, dict):
            raise InvalidPolicyDecisionInputError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )
        if not isinstance(resolved_policies, list):
            raise InvalidPolicyDecisionInputError(
                f"resolved_policies must be a list, got {type(resolved_policies).__name__}"
            )
        for resolved in resolved_policies:
            if not isinstance(resolved, ResolvedPolicy):
                raise InvalidPolicyDecisionInputError(
                    f"every entry in resolved_policies must be a ResolvedPolicy, got {type(resolved).__name__}"
                )

        provenance = [
            PolicyEvaluationTrace(
                resolved=resolved, decision=self._evaluator.evaluate(resolved.policy, action_context)
            )
            for resolved in resolved_policies
        ]

        matched = [trace.decision for trace in provenance if trace.decision.rule_id is not None]

        denials = [decision for decision in matched if decision.effect == DENY]
        if denials:
            return PolicyDecision(
                decision=DENY,
                matched_rules=denials,
                reasons=[decision.reason for decision in denials],
                provenance=provenance,
            )

        allowances = [decision for decision in matched if decision.effect == ALLOW]
        if allowances:
            return PolicyDecision(
                decision=ALLOW,
                matched_rules=allowances,
                reasons=[decision.reason for decision in allowances],
                provenance=provenance,
            )

        default_reason = (
            _DEFAULT_DENY_REASON_WITH_POLICIES if provenance else _DEFAULT_DENY_REASON_NO_POLICIES
        )
        return PolicyDecision(
            decision=DENY,
            matched_rules=[],
            reasons=[default_reason],
            provenance=provenance,
        )
