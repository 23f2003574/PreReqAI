from datetime import datetime, timezone

from backend.agent_policy_enforcement import LLMAgentPolicyEnforcedExecutionService
from backend.agent_policy_risk_classification import LLMAgentPolicyRiskClassifier
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine
from backend.llm.tool_execution import DENIED

from .gate import LLMAgentRiskApprovalGate
from .models import APPROVED


class LLMAgentRiskGatedExecutionService(LLMAgentPolicyEnforcedExecutionService):
    """backend.agent_policy_enforcement.LLMAgentPolicyEnforcedExecutionService
    (Commit #4 of the base series), unchanged, with exactly one more
    pre-execution gate layered in front of it: Commit #1-#5's own risk
    assessment -> classification -> threshold -> decision -> approval
    pipeline.

    Not a second execution pipeline: this subclasses the real
    LLMAgentPolicyEnforcedExecutionService rather than reimplementing it,
    so every existing gate underneath (Commit #1-#4 policy enforcement,
    plan validation, dependency completion, and the whole
    backend.llm.tool_orchestration pipeline) still runs exactly as
    before -- execute_step() here only adds a check *before* any of
    that, the same "gate, then delegate" shape
    LLMAgentPolicyEnforcedExecutionService itself already established
    for its own single gate. When the risk decision is ALLOW (or REVIEW
    resolved to APPROVED), this method's own logic ends there and
    super().execute_step() carries out the rest completely unchanged --
    including its own, separate policy enforcement check, run a second
    time. This is the same "extra pure, side-effect-free call, in
    exchange for never touching an already-shipped commit's tested
    internals" tradeoff backend.agent_policy_audit's own
    LLMAgentPolicyAuditedExecutionService already accepted for exactly
    this reason.

    Every decision -- ALLOW, REVIEW, and DENY alike -- is routed through
    the same Commit #5 LLMAgentRiskApprovalGate.evaluate() call, rather
    than only calling it for REVIEW: Commit #5's own evaluate() already
    resolves ALLOW/DENY to an immediate APPROVED/REJECTED
    ApprovalRequirement, so this keeps the gate's own store a complete
    record of every decision this boundary ever made (see Rules:
    "deny cannot be approved into execution" -- a DENY's auto-REJECTED
    requirement is exactly as unapprovable through the gate as a real
    human rejection is), not just the ones that paused for review, and
    it means this method itself never has to special-case DENY
    separately from REVIEW.

    Only requirement.status == APPROVED lets this method fall through to
    super().execute_step() and actually run the action -- anything else
    (a fresh or still-pending REQUIRED, a REJECTED, or a lapsed EXPIRED)
    is recorded as a DENIED step via the base class's own inherited
    _record(), never handed to tool_orchestration_service. This is what
    "review actions pause ... execution until approved" means at the
    real boundary: a REVIEW action is blocked on *every* execute_step()
    call until a human approve()s the exact same action/context through
    the gate directly (see LLMAgentRiskApprovalGate's own evaluate()
    docstring for how a retry reaches the same requirement).

    Preserves the base class's own documented "never raises for a
    refused or failing call" contract exactly: an unknown plan_id/
    step_id still raises (propagated from the base class's own
    planning_service.get()/_find_step()), but a risk-blocked action is
    always a normal LLMAgentStepExecution with status DENIED, never an
    exception.
    """

    def __init__(
        self,
        planning_service,
        validation_service,
        tool_orchestration_service,
        enforcement,
        scope_for_plan,
        risk_assessor,
        approval_gate: LLMAgentRiskApprovalGate,
        risk_classifier: LLMAgentPolicyRiskClassifier = None,
        threshold_service=None,
        decision_engine: LLMAgentPolicyRiskDecisionEngine = None,
    ):
        """
        Args:
            risk_assessor: Commit #1's LLMAgentPolicyRiskAssessor
            approval_gate: Commit #5's LLMAgentRiskApprovalGate
            risk_classifier: Commit #2's LLMAgentPolicyRiskClassifier,
                defaulting to a plain instance
            threshold_service: Optional Commit #3
                LLMAgentPolicyRiskThresholdService, read via
                get(scope_id); None means every scope uses Commit #4's
                own default thresholds (see
                LLMAgentPolicyRiskDecisionEngine.decide())
            decision_engine: Commit #4's LLMAgentPolicyRiskDecisionEngine,
                defaulting to a plain instance
        """
        super().__init__(planning_service, validation_service, tool_orchestration_service, enforcement, scope_for_plan)
        self._risk_assessor = risk_assessor
        self._risk_classifier = risk_classifier or LLMAgentPolicyRiskClassifier()
        self._threshold_service = threshold_service
        self._decision_engine = decision_engine or LLMAgentPolicyRiskDecisionEngine()
        self._approval_gate = approval_gate

    def execute_step(self, plan_id: str, step_id: str, subject, timeout: float = None):
        """Run exactly one step of `plan_id`, as
        LLMAgentPolicyEnforcedExecutionService.execute_step() already
        does, after first resolving and, for REVIEW, gating this action
        through Commit #5's own approval workflow.

        Never raises for a refused, denied, unapproved, or failing call,
        exactly like the base class -- only an unknown plan_id or
        step_id raises.
        """
        plan = self._planning_service.get(plan_id)
        step = self._find_step(plan, step_id)
        started_at = datetime.now(timezone.utc)

        action_context = {
            "scope_id": self._scope_for_plan(plan_id),
            "plan_id": plan_id,
            "step_id": step_id,
            "tool_name": step.tool_name,
            "arguments": dict(step.arguments),
            "subject": subject,
        }

        assessment = self._risk_assessor.assess(action_context)
        classification = self._risk_classifier.classify(assessment)
        thresholds = (
            self._threshold_service.get(action_context["scope_id"])
            if self._threshold_service is not None
            else None
        )
        decision = self._decision_engine.decide(action_context, classification, thresholds)

        # Every decision -- ALLOW, REVIEW, and DENY alike -- is routed
        # through the same gate, rather than only calling it for REVIEW:
        # this is what gives DENY its own recorded, unapprovable
        # ApprovalRequirement too (see LLMAgentRiskApprovalGate.evaluate()
        # for why ALLOW/DENY resolve immediately), so the gate's own
        # store is a complete record of every decision this boundary ever
        # made, not just the ones that paused for review.
        requirement = self._approval_gate.evaluate(decision, action_context)
        if requirement.status != APPROVED:
            return self._record(
                plan_id, step_id, DENIED, None,
                f"blocked pending approval (request_id={requirement.request_id}, "
                f"status={requirement.status})",
                started_at,
            )

        return super().execute_step(plan_id, step_id, subject, timeout=timeout)
