from backend.agent_capability_registry import LLMAgentCapabilityRegistry, UnknownCapabilityError
from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyService
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_policy_risk_thresholds import (
    DEFAULT_DENY_AT,
    DEFAULT_REVIEW_AT,
    REVIEW,
    LLMAgentPolicyRiskThresholdService,
    resolve_action,
)
from backend.agent_risk_profile_resolution import LLMAgentRiskProfileResolver

from .models import CapabilityExecutionPolicyResult


class InvalidCapabilityExecutionPolicyError(ValueError):
    """Raised when evaluate() is given a missing/blank agent_id/
    capability_id/scope_id, or a context that is not a dict."""


class LLMAgentCapabilityExecutionPolicy:
    """Evaluates whether a specific agent/capability/scope/context
    execution attempt is authorized, by composing this repository's own
    existing policy, risk, and capability infrastructure -- never a
    second authorization system.

    The base allow/deny verdict is entirely
    backend.agent_policy_resolution.LLMAgentPolicyResolver +
    backend.agent_policy_decision.LLMAgentPolicyDecisionEngine, the
    exact same scope-isolated policy resolution and multi-policy,
    explicit-deny-always-wins aggregation every other consumer of the
    base policy series already uses -- not the lighter, default-include
    matching backend.agent_capability_resolution.LLMAgentCapabilityResolver
    (Commit #2) applies for capability *visibility*. That distinction is
    deliberate: Commit #2 answers "can this agent see this capability at
    all", Commit #5 (compatibility) answers "can this capability
    generally operate here", and this commit answers "is this exact
    execution attempt authorized right now" -- the stricter,
    default-deny gate Commit #5's own docstring already said a caller
    must still run before actually invoking a capability.

    Risk-profile restrictions (Rule: "respect existing risk-profile...
    decisions") are folded in through backend.agent_risk_profile_resolution.
    LLMAgentRiskProfileResolver + backend.agent_policy_risk_thresholds.
    resolve_action() -- both optional collaborators, reused only "when
    already represented" (Rule), i.e. only when a caller actually
    supplies them; when omitted, no risk layer runs at all and the base
    policy decision is the whole answer. A risk level of DEFAULT_DENY_AT
    or above can only ever add a denial on top of an ALLOW base
    decision, never remove one the base policy already decided (Rule:
    "explicit denials must remain denials").

    backend.llm.tool_permissions.LLMToolPermissionService was
    deliberately NOT integrated: it authorizes an LLMToolInvocationPlan
    against a name registered in the unrelated backend.llm.tools
    registry, a different identifier namespace this commit's own
    capability_id has no guaranteed relationship to -- fabricating a
    synthetic plan/tool registration just to call it would itself be the
    kind of invented coupling this module's own "no invented runtime
    infrastructure" constraint rules out. In this domain, the base
    agent-policy stack above already *is* the "permission decision"
    system Rule: "respect existing... permission decisions" refers to
    (backend.agent_policy_engine.LLMAgentPolicyEvaluator's own docstring
    already describes itself as following tool_permissions'
    authorization model, applied to agent actions instead of tool
    calls).

    evaluate() only ever reads (LLMAgentPolicyResolver.resolve(),
    LLMAgentPolicyDecisionEngine.decide(), LLMAgentRiskProfileResolver.
    resolve(), LLMAgentPolicyRiskThresholdService.get(),
    LLMAgentCapabilityRegistry.get()) -- no policy, risk profile,
    threshold, or capability is ever created, changed, or removed, and
    no capability is executed. The same (agent_id, capability_id,
    scope_id, context, and current policy/risk/capability state) always
    produces the same CapabilityExecutionPolicyResult.
    """

    def __init__(
        self,
        policy_service: LLMAgentPolicyService,
        decision_engine: LLMAgentPolicyDecisionEngine = None,
        risk_profile_resolver: LLMAgentRiskProfileResolver = None,
        risk_threshold_service: LLMAgentPolicyRiskThresholdService = None,
        capability_registry: LLMAgentCapabilityRegistry = None,
    ):
        self._policy_resolver = LLMAgentPolicyResolver(policy_service)
        self._decision_engine = decision_engine if decision_engine is not None else LLMAgentPolicyDecisionEngine()
        self._risk_profile_resolver = risk_profile_resolver
        self._risk_threshold_service = risk_threshold_service
        self._capability_registry = capability_registry

    def evaluate(
        self, agent_id: str, capability_id: str, scope_id: str, context: dict = None
    ) -> CapabilityExecutionPolicyResult:
        """Whether agent_id may execute capability_id in scope_id/context
        right now.

        Raises:
            InvalidCapabilityExecutionPolicyError: If agent_id,
                capability_id, or scope_id is missing/blank, or context
                is given and is not a dict
        """
        self._validate_id(agent_id, "agent_id")
        self._validate_id(capability_id, "capability_id")
        self._validate_id(scope_id, "scope_id")
        if context is None:
            context = {}
        elif not isinstance(context, dict):
            raise InvalidCapabilityExecutionPolicyError(
                f"context must be a dict, got {type(context).__name__}"
            )

        action = dict(context)
        action.update(
            {"agent_id": agent_id, "capability_id": capability_id, "tool_name": capability_id, "scope_id": scope_id}
        )
        if self._capability_registry is not None:
            try:
                action["category"] = self._capability_registry.get(capability_id).category
            except UnknownCapabilityError:
                pass

        resolved_policies = self._policy_resolver.resolve(scope_id)
        policy_decision = self._decision_engine.decide(action, resolved_policies)

        decision = policy_decision.decision
        matched_policies = list(policy_decision.matched_rules)
        reasons = list(policy_decision.reasons)
        denials = list(policy_decision.reasons) if decision == DENY else []
        warnings = []

        if self._risk_profile_resolver is not None:
            resolved_risk = self._risk_profile_resolver.resolve(scope_id, action)
            if resolved_risk is None:
                reasons.append(f"no active risk profile configured for scope {scope_id!r}; risk layer skipped")
            else:
                if self._risk_threshold_service is not None:
                    thresholds = self._risk_threshold_service.get(scope_id)
                    review_at, deny_at = thresholds.review_at, thresholds.deny_at
                else:
                    review_at, deny_at = DEFAULT_REVIEW_AT, DEFAULT_DENY_AT

                risk_action = resolve_action(resolved_risk.level, review_at, deny_at)
                risk_reason = (
                    f"risk profile resolved level={resolved_risk.level!r} ({resolved_risk.reason}); "
                    f"threshold action={risk_action!r}"
                )
                reasons.append(risk_reason)

                if risk_action == DENY:
                    decision = DENY
                    denials.append(risk_reason)
                elif risk_action == REVIEW:
                    warnings.append(risk_reason)

        return CapabilityExecutionPolicyResult(
            allowed=decision == ALLOW,
            decision=decision,
            matched_policies=matched_policies,
            denials=denials,
            warnings=warnings,
            reasons=reasons,
        )

    @staticmethod
    def _validate_id(value, field_name):
        if not value or not isinstance(value, str):
            raise InvalidCapabilityExecutionPolicyError(
                f"{field_name} is required and must be a non-empty string"
            )
