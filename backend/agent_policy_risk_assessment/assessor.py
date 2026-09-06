from backend.agent_policy_engine import DENY
from backend.agent_policy_enforcement import (
    LLMAgentPolicyEnforcement,
    PolicyEvaluationFailedError,
    is_blocking,
)
from backend.llm.tools import LLMToolRegistryService, UnknownToolError

from .models import MAX_SCORE, RiskAssessment, level_for_score

# Weights are local to this assessor, the same way
# backend.session.execution_policy_risk_service's own VIOLATION_WEIGHT/
# UNRESOLVED_CONFLICT_WEIGHT/etc. are -- only the LEVEL_*/level_for_score
# threshold model itself is shared, not a weighting scheme, since no
# other repo module scores an *action* (as opposed to a session) this way.
#
# POLICY_DENIAL_WEIGHT and POLICY_EVALUATION_FAILURE_WEIGHT are each set
# to MAX_SCORE so that either one alone always reaches LEVEL_CRITICAL,
# regardless of any other factor present -- this is what "explicit
# policy denial remains authoritative" and "fail closed on evaluation
# failure" (backend.agent_policy_enforcement's own established
# convention) mean in score terms, rather than a separate override of
# risk_level that could disagree with risk_factors/level_for_score.
POLICY_DENIAL_WEIGHT = MAX_SCORE
POLICY_EVALUATION_FAILURE_WEIGHT = MAX_SCORE
UNREGISTERED_TOOL_WEIGHT = 30
DISABLED_TOOL_WEIGHT = 40
PRIOR_DENIED_ACTION_WEIGHT = 15

_WEIGHTS = {
    "policy_denial": POLICY_DENIAL_WEIGHT,
    "policy_evaluation_failed": POLICY_EVALUATION_FAILURE_WEIGHT,
    "unregistered_tool": UNREGISTERED_TOOL_WEIGHT,
    "disabled_tool": DISABLED_TOOL_WEIGHT,
    "prior_denied_actions": PRIOR_DENIED_ACTION_WEIGHT,
}


class InvalidActionContextError(ValueError):
    """Raised when assess() is given an action_context that is not a dict."""


class LLMAgentPolicyRiskAssessor:
    """Pre-execution risk layer for one agent action, evaluated entirely
    from evidence the repository already has on record.

    Not a second risk or policy framework: every actual decision is
    delegated to collaborators this repository already ships --

    - policy: backend.agent_policy_enforcement.LLMAgentPolicyEnforcement
      (Commits #1-#4 of the base agent_policy_* series), the exact same
      resolve-then-decide call
      backend.agent_policy_enforcement.LLMAgentPolicyEnforcedExecutionService
      already runs immediately before a step actually executes. This is
      "the real action boundary": assess() calls it and nothing else for
      the policy verdict, and never calls tool_orchestration or anything
      that would actually run the action.
    - tool: backend.llm.tools.LLMToolRegistryService (optional), the
      existing tool catalog -- whether action_context's own tool_name is
      registered at all, and whether it is currently enabled.
    - security: backend.agent_policy_audit.LLMAgentPolicyAuditService
      (optional), this scope's own already-redacted decision history --
      prior DENY verdicts recorded for this scope are the closest thing
      the agent-policy domain already has to "existing security
      findings" (the same denied-enforcement-history signal
      backend.session.execution_policy_risk_service already scores for a
      session, applied here to a scope via the sibling audit trail this
      series' own Commit #7 built).
    - execution context: action_context itself (scope_id/tool_name/
      arguments/subject/etc, the exact shape
      LLMAgentPolicyEnforcedExecutionService already builds) is the only
      thing describing the action; nothing here invents a field
      action_context does not carry.

    tool_registry and audit_service are optional, duck-typed
    collaborators that degrade gracefully when omitted -- the same
    "optional collaborator, degrades gracefully" pattern already used
    throughout the agent_policy_* and agent_policy_template_* series
    (e.g. LLMAgentPolicyDeploymentVerifier's optional version_service):
    a factor either of them would supply is simply omitted from
    risk_factors, never guessed or defaulted to zero, when the
    collaborator is not configured or action_context does not name the
    field it needs (a missing tool_name, or a missing scope_id once
    policy evaluation itself has already succeeded).

    assess() is deterministic and side-effect free: it never mutates
    action_context, a policy, a tool definition, or an audit record, and
    it never executes the action or calls an LLM. The same
    (action_context, underlying repository state) always produces an
    == RiskAssessment.
    """

    def __init__(
        self,
        enforcement: LLMAgentPolicyEnforcement,
        audit_service=None,
        tool_registry: LLMToolRegistryService = None,
    ):
        """
        Args:
            enforcement: The Commit #1-#4 policy enforcement pipeline
                used to resolve and evaluate action_context -- required,
                since policy is this assessor's primary, authoritative
                source of evidence
            audit_service: Optional backend.agent_policy_audit.
                LLMAgentPolicyAuditService, read via
                list_for_scope(scope_id) for this scope's own recorded
                DENY history
            tool_registry: Optional backend.llm.tools.
                LLMToolRegistryService, read via get(tool_name) for
                whether the requested tool is registered and enabled
        """
        self._enforcement = enforcement
        self._audit_service = audit_service
        self._tool_registry = tool_registry

    @staticmethod
    def _score(factors: dict) -> int:
        raw = sum(factors.get(name, 0) * weight for name, weight in _WEIGHTS.items())
        return min(raw, MAX_SCORE)

    def _tool_evidence(self, tool_name, factors: dict, reasons: list) -> dict:
        if self._tool_registry is None or not tool_name:
            return None

        try:
            tool = self._tool_registry.get(tool_name)
        except UnknownToolError:
            factors["unregistered_tool"] = 1
            reasons.append(f"tool {tool_name!r} is not registered")
            return {"tool_name": tool_name, "registered": False, "enabled": False}

        factors["unregistered_tool"] = 0
        factors["disabled_tool"] = 0 if tool.enabled else 1
        if not tool.enabled:
            reasons.append(f"tool {tool_name!r} is registered but disabled")
        return {"tool_name": tool_name, "registered": True, "enabled": tool.enabled}

    def _prior_denied_actions(self, scope_id, factors: dict, reasons: list):
        if self._audit_service is None or not scope_id:
            return None

        prior_denied = [
            audit for audit in self._audit_service.list_for_scope(scope_id) if audit.decision == DENY
        ]
        if prior_denied:
            factors["prior_denied_actions"] = len(prior_denied)
            reasons.append(
                f"scope {scope_id!r} has {len(prior_denied)} prior denied action(s) on record"
            )
        return prior_denied

    def assess(self, action_context: dict) -> RiskAssessment:
        """Assess the risk of one agent action, without executing it.

        action_context is the exact shape
        LLMAgentPolicyEnforcedExecutionService already builds before a
        step runs: scope_id/plan_id/step_id/tool_name/arguments/subject,
        though only scope_id and tool_name are ever read directly here --
        every other field is passed through untouched to policy
        evaluation and preserved in provenance.

        Raises:
            InvalidActionContextError: If action_context is not a dict
        """
        if not isinstance(action_context, dict):
            raise InvalidActionContextError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )

        factors: dict = {}
        reasons: list = []
        provenance: dict = {"action_context": dict(action_context)}

        try:
            decision = self._enforcement.enforce(action_context)
        except PolicyEvaluationFailedError as error:
            # Rule: fail closed, the same discipline
            # LLMAgentPolicyEnforcedExecutionService already applies at
            # the real execution boundary -- an assessment that cannot
            # even resolve/evaluate policy must never read as low risk.
            factors["policy_evaluation_failed"] = 1
            reasons.append(f"policy evaluation failed; failing closed ({error})")
            provenance["policy_decision"] = None
            provenance["policy_evaluation_error"] = str(error)
            provenance["tool_status"] = None
            provenance["prior_denied_actions"] = None
            return RiskAssessment(
                risk_level=level_for_score(self._score(factors)),
                risk_factors=factors,
                matched_policies=[],
                matched_security_findings=[],
                reasons=reasons,
                provenance=provenance,
            )

        provenance["policy_decision"] = decision
        matched_policies = list(decision.matched_rules)

        if is_blocking(decision):
            factors["policy_denial"] = 1
            reasons.extend(decision.reasons)

        provenance["tool_status"] = self._tool_evidence(
            action_context.get("tool_name"), factors, reasons
        )

        prior_denied = self._prior_denied_actions(action_context.get("scope_id"), factors, reasons)
        provenance["prior_denied_actions"] = prior_denied
        matched_security_findings = list(prior_denied) if prior_denied else []

        if not reasons:
            reasons.append("no elevated risk factors found")

        return RiskAssessment(
            risk_level=level_for_score(self._score(factors)),
            risk_factors=factors,
            matched_policies=matched_policies,
            matched_security_findings=matched_security_findings,
            reasons=reasons,
            provenance=provenance,
        )
