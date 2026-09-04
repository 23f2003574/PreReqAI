from datetime import datetime

from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine, PolicyDecision
from backend.agent_policy_engine import ALLOW, DENY

from .service import LLMAgentPolicyExceptionService


class LLMAgentPolicyExceptionAwareDecisionEngine:
    """A drop-in replacement for Commit #3's own
    LLMAgentPolicyDecisionEngine (same decide(action_context,
    resolved_policies) -> PolicyDecision signature) that additionally
    lets an active, narrowly-matching Commit #5 LLMAgentPolicyException
    lift one specific policy's explicit denial.

    Not a second decision engine: every actual policy verdict is still
    entirely Commit #3's own decide() -- called first, unchanged, and
    returned completely as-is whenever there is no explicit denial for an
    exception to possibly except (an ALLOW, or a DENY reached purely
    because nothing applied at all -- Commit #3's own aggregate default,
    which no exception targets, since an exception always names one
    specific policy_id). Only when decide() found at least one explicit
    DENY does this class ever consult
    LLMAgentPolicyExceptionService.applicable() at all, once per denying
    policy_id.

    "Any explicit deny blocks the action" still holds across exceptions:
    if even one denying policy has no applicable exception, the original
    DENY is returned completely unchanged -- an exception excepts the
    one policy it was explicitly granted against, never the action
    outright, so it can never quietly cover for an unrelated policy's
    denial. Only once *every* explicit denial has an applicable exception
    does this class recompute the verdict from Commit #3's own full
    provenance (every resolved policy's decision is already preserved in
    PolicyDecision.provenance, deny or allow, matched or not) -- an
    explicit ALLOW found there still wins on its own merits, and the
    result is ALLOW, with matched_rules never including a decision
    covered by an exception (its relief is instead recorded in
    exceptions_applied). Where nothing ever explicitly allowed the
    action either, the exception(s) alone are what carries it to ALLOW,
    exactly the reason a policy exception mechanism exists at all --
    "default behavior remains deny when no valid exception applies" (see
    Commit #5's own rule) implies its converse: default behavior properly
    becomes allow once a valid, applicable exception *does* apply to
    every explicit denial standing in the way.

    Never mutates a policy, a ResolvedPolicy, an LLMAgentPolicyException,
    or action_context -- this is pure decision-making layered on top of
    Commit #3's own, exactly as Commit #3 itself is layered on Commit #1.
    No LLM call is made anywhere in this evaluation.
    """

    def __init__(
        self,
        exception_service: LLMAgentPolicyExceptionService,
        decision_engine: LLMAgentPolicyDecisionEngine = None,
        now: datetime = None,
    ):
        self._exception_service = exception_service
        self._decision_engine = decision_engine or LLMAgentPolicyDecisionEngine()
        self._now = now

    def decide(self, action_context: dict, resolved_policies: list) -> PolicyDecision:
        raw = self._decision_engine.decide(action_context, resolved_policies)

        matched = [trace.decision for trace in raw.provenance if trace.decision.rule_id is not None]
        denials = [decision for decision in matched if decision.effect == DENY]

        if not denials:
            # ALLOW, or a DENY reached purely by the aggregate default --
            # either way there is no explicit denial for an exception to
            # except, so Commit #3's own decision stands unchanged.
            return raw

        scope_id = action_context.get("scope_id")
        remaining_denials = []
        exceptions_applied = []
        for denial in denials:
            applicable = self._exception_service.applicable(
                scope_id, denial.policy_id, action_context, now=self._now
            )
            if applicable:
                exceptions_applied.append(applicable[0])
            else:
                remaining_denials.append(denial)

        if remaining_denials:
            # at least one explicit denial has no applicable exception --
            # deny still stands, unchanged, exactly Commit #3's own
            # decision.
            return raw

        allowances = [decision for decision in matched if decision.effect == ALLOW]
        exception_reasons = [
            f"exception {exception.exception_id!r} granted relief from policy "
            f"{exception.policy_id!r}'s denial: {exception.reason}"
            for exception in exceptions_applied
        ]
        return PolicyDecision(
            decision=ALLOW,
            matched_rules=allowances,
            reasons=[decision.reason for decision in allowances] + exception_reasons,
            provenance=raw.provenance,
            exceptions_applied=exceptions_applied,
        )
