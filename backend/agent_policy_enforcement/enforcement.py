from backend.agent_policy_decision import (
    InvalidPolicyDecisionInputError,
    LLMAgentPolicyDecisionEngine,
    PolicyDecision,
)
from backend.agent_policy_engine import DENY
from backend.agent_policy_resolution import LLMAgentPolicyResolver


class PolicyEvaluationFailedError(RuntimeError):
    """Raised by enforce() when resolving or evaluating policy itself
    fails unexpectedly -- never for a legitimate ALLOW/DENY verdict, only
    for a genuine internal failure (a misconfigured resolver, a
    scope_for_execution/scope_for_plan mapping that raises, or anything
    else this method cannot anticipate). Carries the original exception
    as __cause__.

    Kept distinct from an ordinary DENY PolicyDecision on purpose: a
    caller integrating enforce() at a real execution boundary (see
    LLMAgentPolicyEnforcedExecutionService) must be able to tell "policy
    says no" apart from "policy could not be evaluated at all", since the
    two are handled differently there -- an ordinary no-match DENY leaves
    existing behavior unchanged (see is_blocking()), while this error is
    always treated as fail-closed, the same "unknown must never silently
    become ALLOW" discipline
    backend.llm.sensitive_data_policy.LLMSensitiveDataPolicyService
    already applies to an unrecognized data_type.
    """


def is_blocking(decision: PolicyDecision) -> bool:
    """Whether a PolicyDecision should actually stop an action at a
    pre-existing execution boundary from running.

    Deliberately narrower than `decision.decision == DENY` alone:
    Commit #3's own LLMAgentPolicyDecisionEngine.decide() already returns
    DENY whenever nothing applicable was found at all (no policy exists
    for the scope, or no rule in any resolved policy matched) -- the
    exact deny-by-default convention
    backend.llm.tool_permissions.LLMToolPermissionService.authorize()
    already uses for a brand-new permission system, and the correct,
    unchanged behavior for Commit #3 used on its own. But Commit #4 is
    layered onto an *already working* execution pipeline, where "no
    applicable policy blocks it" (Commit #4's own rule) must leave
    existing behavior alone rather than newly denying every action
    nobody has written a policy for yet. So only a DENY reached through
    an actual matched rule -- decision.matched_rules is non-empty --
    counts as "blocks it" here; a DENY reached purely by the aggregate
    default does not.
    """
    return decision.decision == DENY and bool(decision.matched_rules)


class LLMAgentPolicyEnforcement:
    """The single point a caller asks "is this action allowed" before it
    runs, composing Commit #1-#3 into one fixed pipeline rather than a
    new one: resolve() (Commit #2) the policies applicable to
    action_context's own scope_id, then decide() (Commit #3) the action
    against them. This mirrors
    backend.llm.security_policy.LLMSecurityPolicyService's own
    "compose, don't reimplement" shape at the LLM request/response
    boundary, applied here to the agent action boundary instead.

    enforce() never raises for a legitimate policy verdict, allow or
    deny -- it always returns a PolicyDecision for one, so "expose the
    decision/reason to the caller" never requires guessing from an
    exception what happened. It raises PolicyEvaluationFailedError only
    when resolving or evaluating policy itself fails unexpectedly (a
    misconfigured resolver, a bad scope_for_execution/scope_for_plan
    mapping, or anything else this method cannot anticipate) -- kept
    distinct from a normal DENY on purpose, so a caller at a real
    execution boundary can fail closed on a genuine failure without that
    same handling swallowing an ordinary, already-correct no-match DENY
    (see is_blocking()). Only a malformed action_context (not a dict at
    all) raises a different error, InvalidPolicyDecisionInputError --
    that is a caller bug, not a policy-evaluation failure.

    enforce() reads scope_id out of action_context itself (the same
    dict a caller also uses for tool_name/arguments/etc.) rather than
    taking it as a second parameter, so its signature stays exactly
    Commit #4's own enforce(action_context) -> PolicyDecision. A missing
    or invalid scope_id is not treated specially: it surfaces as
    whatever LLMAgentPolicyResolver.resolve()/LLMAgentPolicyService.list()
    already raises for it, wrapped into PolicyEvaluationFailedError like
    any other evaluation failure.

    Never mutates action_context, a policy, or a ResolvedPolicy -- this
    is pure decision-making, exactly as Commit #1's evaluator and
    Commit #3's decision engine already are. No LLM call is made
    anywhere in this evaluation.
    """

    def __init__(
        self,
        resolver: LLMAgentPolicyResolver,
        decision_engine: LLMAgentPolicyDecisionEngine = None,
    ):
        self._resolver = resolver
        self._decision_engine = decision_engine or LLMAgentPolicyDecisionEngine()

    def enforce(self, action_context: dict) -> PolicyDecision:
        """Resolve and evaluate every policy applicable to
        action_context["scope_id"], returning one authoritative
        PolicyDecision.

        Raises:
            InvalidPolicyDecisionInputError: If action_context is not a
                dict
            PolicyEvaluationFailedError: If resolving or evaluating
                policy itself fails unexpectedly
        """
        if not isinstance(action_context, dict):
            raise InvalidPolicyDecisionInputError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )

        scope_id = action_context.get("scope_id")

        try:
            resolved_policies = self._resolver.resolve(scope_id, action_context)
            return self._decision_engine.decide(action_context, resolved_policies)
        except Exception as error:
            raise PolicyEvaluationFailedError(
                f"policy evaluation failed ({error.__class__.__name__}: {error})"
            ) from error
