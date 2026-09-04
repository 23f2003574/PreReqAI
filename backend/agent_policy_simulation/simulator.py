from datetime import datetime, timezone

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement, is_blocking
from backend.agent_policy_decision import InvalidPolicyDecisionInputError

from .models import PolicyConflict, PolicySimulationResult


class LLMAgentPolicySimulator:
    """Previews what LLMAgentPolicyEnforcement.enforce() would decide for
    an action, without ever executing anything, mutating any policy,
    exception, or agent state, or reaching a real execution boundary.

    Not a second evaluation path: simulate() calls the exact same
    enforcement instance a caller uses for real enforcement decisions --
    Commit #1's evaluator, Commit #2's resolver, Commit #3's decision
    engine (optionally Commit #5's exception-aware one), and Commit #4's
    fail-closed handling all run completely unchanged and exactly once.
    There is no duplicated resolution, matching, or aggregation logic
    here; this class only reshapes the one PolicyDecision that call
    already produced into a simulation-facing PolicySimulationResult,
    plus a small amount of pure, read-only reporting
    (matched_policies/conflicts) computed from that same PolicyDecision's
    own provenance.

    Zero execution side effects, by construction: this class never holds
    a reference to a tool orchestrator, a step-execution service, or
    anything else capable of actually running an action, so there is
    nothing here that could execute one even by mistake.
    LLMAgentPolicyEnforcement.enforce() itself is already pure (Commit
    #4), so calling it here mutates nothing either. Deterministic for
    identical inputs, for the same reason: enforce() already is.
    """

    def __init__(self, enforcement: LLMAgentPolicyEnforcement):
        self._enforcement = enforcement

    def simulate(self, action_context: dict) -> PolicySimulationResult:
        """Preview the enforcement outcome for `action_context`.

        Raises:
            InvalidPolicyDecisionInputError: If action_context is not a
                dict (propagated from enforce(), not wrapped)
            PolicyEvaluationFailedError: If resolving or evaluating
                policy itself fails unexpectedly (propagated from
                enforce(), not wrapped -- a simulation of a broken policy
                configuration must surface that failure too, not mask it
                behind a default preview)
        """
        if not isinstance(action_context, dict):
            raise InvalidPolicyDecisionInputError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )

        decision = self._enforcement.enforce(action_context)

        matched = [trace.decision for trace in decision.provenance if trace.decision.rule_id is not None]
        matched_policies = [entry.policy_id for entry in matched]

        allowances = [entry for entry in matched if entry.effect == ALLOW]
        denials = [entry for entry in matched if entry.effect == DENY]
        conflicts = [
            PolicyConflict(allow=allow_decision, deny=deny_decision)
            for allow_decision in allowances
            for deny_decision in denials
        ]

        return PolicySimulationResult(
            action_context=dict(action_context),
            would_allow=not is_blocking(decision),
            final_decision=decision,
            matched_policies=matched_policies,
            matched_rules=list(decision.matched_rules),
            applicable_exceptions=list(decision.exceptions_applied),
            conflicts=conflicts,
            reasons=list(decision.reasons),
            provenance=list(decision.provenance),
            simulated_at=datetime.now(timezone.utc),
        )
