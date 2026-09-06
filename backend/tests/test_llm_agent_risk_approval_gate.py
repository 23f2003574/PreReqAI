from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
from backend.agent_policy_engine import ALLOW as POLICY_ALLOW
from backend.agent_policy_engine import DENY as POLICY_DENY
from backend.agent_policy_engine import LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_policy_risk_approval import (
    APPROVED,
    EXPIRED,
    REJECTED,
    REQUIRED,
    SYSTEM_ACTOR,
    ExpiredApprovalError,
    InvalidApprovalTransitionError,
    LLMAgentRiskApprovalGate,
    LLMAgentRiskGatedExecutionService,
    UnknownApprovalRequestError,
)
from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW, LLMAgentPolicyRiskAssessor
from backend.agent_policy_risk_classification import LLMAgentPolicyRiskClassifier, RiskClassification
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import DENIED, SUCCEEDED, LLMToolExecutionService
from backend.llm.tool_idempotency import LLMToolIdempotencyService
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_orchestration import LLMToolCallingOrchestrationService
from backend.llm.tool_permissions import ANY_SUBJECT, LLMToolPermissionPolicy, LLMToolPermissionService
from backend.llm.tool_results import LLMToolResultService
from backend.llm.tool_retry import LLMToolRetryPolicy, LLMToolRetryService
from backend.llm.tools import LLMToolRegistryService

SCHEMA = {"type": "object", "properties": {"topic": {"type": "string"}}, "required": []}
ACTION_CONTEXT = {"scope_id": "notebook-1", "plan_id": "plan-1", "step_id": "step-1", "tool_name": "lookup", "arguments": {}}


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _decision_for_level(risk_level, risk_factors=None, reasons=None):
    classification = RiskClassification(
        risk_level=risk_level,
        confidence="HIGH",
        evidence={},
        risk_factors=risk_factors or {},
        reasons=reasons or ["synthetic"],
        provenance={},
    )
    return LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification)


def _allow_decision():
    return _decision_for_level(LEVEL_LOW)  # LOW under default thresholds -> ALLOW


def _deny_decision():
    policy_service = LLMAgentPolicyService()
    policy_service.create("notebook-1", "deny-policy", [_rule("deny-lookup", POLICY_DENY, {"tool_name": "lookup"})])
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    assessment = LLMAgentPolicyRiskAssessor(enforcement).assess(ACTION_CONTEXT)
    classification = LLMAgentPolicyRiskClassifier().classify(assessment)
    return LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification)


def _review_decision():
    classification = RiskClassification(
        risk_level=LEVEL_HIGH, confidence="HIGH", evidence={}, risk_factors={"prior_denied_actions": 4},
        reasons=["synthetic high risk"], provenance={},
    )
    return LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification)


# --- allow bypass -----------------------------------------------------------


def test_allow_bypasses_approval():
    gate = LLMAgentRiskApprovalGate()
    requirement = gate.evaluate(_allow_decision(), ACTION_CONTEXT)

    assert requirement.status == APPROVED
    assert requirement.actor == SYSTEM_ACTOR
    assert requirement.resolved_at is not None
    assert requirement.expires_at is None


# --- review requires approval ------------------------------------------------


def test_review_creates_a_required_requirement():
    gate = LLMAgentRiskApprovalGate()
    requirement = gate.evaluate(_review_decision(), ACTION_CONTEXT)

    assert requirement.status == REQUIRED
    assert requirement.actor is None
    assert requirement.expires_at is not None


def test_review_evaluate_is_idempotent_while_pending():
    gate = LLMAgentRiskApprovalGate()
    decision = _review_decision()

    first = gate.evaluate(decision, ACTION_CONTEXT)
    second = gate.evaluate(decision, ACTION_CONTEXT)

    assert first.request_id == second.request_id
    assert second.status == REQUIRED


# --- approval permits execution ----------------------------------------------


def test_approval_permits_execution():
    gate = LLMAgentRiskApprovalGate()
    decision = _review_decision()
    requirement = gate.evaluate(decision, ACTION_CONTEXT)

    approved = gate.approve(requirement.request_id, "reviewer:ada")
    assert approved.status == APPROVED
    assert approved.actor == "reviewer:ada"

    # a retried evaluate() for the identical action_context now reaches
    # the approved requirement, not a fresh pending one
    retried = gate.evaluate(decision, ACTION_CONTEXT)
    assert retried.request_id == requirement.request_id
    assert retried.status == APPROVED


# --- rejection blocks execution -----------------------------------------------


def test_rejection_blocks_execution():
    gate = LLMAgentRiskApprovalGate()
    decision = _review_decision()
    requirement = gate.evaluate(decision, ACTION_CONTEXT)

    rejected = gate.reject(requirement.request_id, "reviewer:ada", "too risky right now")
    assert rejected.status == REJECTED
    assert rejected.reason == "too risky right now"

    retried = gate.evaluate(decision, ACTION_CONTEXT)
    assert retried.request_id == requirement.request_id
    assert retried.status == REJECTED


def test_reject_requires_a_reason():
    gate = LLMAgentRiskApprovalGate()
    requirement = gate.evaluate(_review_decision(), ACTION_CONTEXT)
    with pytest.raises(ValueError):
        gate.reject(requirement.request_id, "reviewer:ada", "")


# --- deny cannot be approved ---------------------------------------------------


def test_deny_auto_rejects_and_cannot_be_approved():
    gate = LLMAgentRiskApprovalGate()
    requirement = gate.evaluate(_deny_decision(), ACTION_CONTEXT)

    assert requirement.status == REJECTED
    assert requirement.actor == SYSTEM_ACTOR

    with pytest.raises(InvalidApprovalTransitionError):
        gate.approve(requirement.request_id, "reviewer:ada")
    with pytest.raises(InvalidApprovalTransitionError):
        gate.reject(requirement.request_id, "reviewer:ada", "already denied")


def test_approving_an_already_approved_requirement_raises():
    gate = LLMAgentRiskApprovalGate()
    requirement = gate.evaluate(_review_decision(), ACTION_CONTEXT)
    gate.approve(requirement.request_id, "reviewer:ada")

    with pytest.raises(InvalidApprovalTransitionError):
        gate.approve(requirement.request_id, "reviewer:bob")


# --- expired approval -----------------------------------------------------------


def test_expired_approval_cannot_be_decided_and_a_fresh_one_is_minted():
    gate = LLMAgentRiskApprovalGate(approval_window=timedelta(seconds=-1))
    decision = _review_decision()
    stale = gate.evaluate(decision, ACTION_CONTEXT)

    assert gate.get(stale.request_id).status == EXPIRED

    with pytest.raises(ExpiredApprovalError):
        gate.approve(stale.request_id, "reviewer:ada")

    fresh = gate.evaluate(decision, ACTION_CONTEXT)
    assert fresh.request_id != stale.request_id
    assert fresh.status == REQUIRED


def test_unknown_request_id_raises():
    gate = LLMAgentRiskApprovalGate()
    with pytest.raises(UnknownApprovalRequestError):
        gate.get("does-not-exist")
    with pytest.raises(UnknownApprovalRequestError):
        gate.approve("does-not-exist", "reviewer:ada")


# --- scope isolation --------------------------------------------------------------


def test_scope_isolation():
    gate = LLMAgentRiskApprovalGate()
    decision = _review_decision()
    context_a = {**ACTION_CONTEXT, "scope_id": "notebook-a"}
    context_b = {**ACTION_CONTEXT, "scope_id": "notebook-b"}

    requirement_a = gate.evaluate(decision, context_a)
    requirement_b = gate.evaluate(decision, context_b)

    assert requirement_a.request_id != requirement_b.request_id
    gate.approve(requirement_a.request_id, "reviewer:ada")

    assert gate.get(requirement_a.request_id).status == APPROVED
    assert gate.get(requirement_b.request_id).status == REQUIRED  # untouched by scope A's approval

    scope_a_ids = {req.request_id for req in gate.store.list_for_scope("notebook-a")}
    scope_b_ids = {req.request_id for req in gate.store.list_for_scope("notebook-b")}
    assert requirement_a.request_id in scope_a_ids
    assert requirement_a.request_id not in scope_b_ids
    assert requirement_b.request_id in scope_b_ids
    assert requirement_b.request_id not in scope_a_ids


# --- provenance ----------------------------------------------------------------


def test_provenance_preserves_actor_decision_evidence_and_timestamps():
    gate = LLMAgentRiskApprovalGate()
    decision = _review_decision()

    requirement = gate.evaluate(decision, ACTION_CONTEXT)
    approved = gate.approve(requirement.request_id, "reviewer:ada")

    assert approved.decision == decision
    assert approved.decision.risk_factors == {"prior_denied_actions": 4}
    assert approved.action_context == ACTION_CONTEXT
    assert approved.actor == "reviewer:ada"
    assert approved.created_at == requirement.created_at
    assert approved.resolved_at is not None
    assert approved.resolved_at >= approved.created_at


# --- execution-boundary integration ----------------------------------------------


class MultiPlanStore:
    def __init__(self):
        self._plans = {}

    def add(self, plan: LLMAgentPlan):
        self._plans[plan.plan_id] = plan

    def get(self, plan_id: str) -> LLMAgentPlan:
        return self._plans[plan_id]


def _step(step_id, tool_name):
    return LLMAgentPlanStep(
        step_id=step_id, action=f"call {tool_name}", tool_name=tool_name,
        arguments={}, depends_on=[], status=READY, errors=[],
    )


def _plan(plan_id, tool_name):
    return LLMAgentPlan(
        plan_id=plan_id, task="a test task", steps=[_step("step-1", tool_name)],
        status=READY, created_at=datetime.now(timezone.utc),
    )


def _harness(tool_name, call_count):
    store = MultiPlanStore()
    registry = LLMToolRegistryService()
    registry.register(tool_name, f"Tool {tool_name}", SCHEMA)

    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    permissions.register(
        LLMToolPermissionPolicy(policy_id="allow-1", tool_name=tool_name, subject=ANY_SUBJECT, allowed=True)
    )

    def handler():
        call_count["calls"] += 1
        return {"found": True}

    execution = LLMToolExecutionService(registry, permissions)
    execution.bind(tool_name, handler)

    idempotency = LLMToolIdempotencyService(execution, permissions)
    control = LLMToolExecutionControlService(execution, idempotency)
    retry = LLMToolRetryService(
        control, execution, LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
        sleeper=lambda seconds: None, idempotency_service=idempotency,
    )
    results = LLMToolResultService()
    orchestrator = LLMToolCallingOrchestrationService(
        invocation_service=invocation, permission_service=permissions, execution_service=execution,
        result_service=results, idempotency_service=idempotency, control_service=control,
        retry_service=retry,
    )
    validation_service = LLMAgentPlanValidationService(store, registry, permissions, invocation_service=invocation)
    return store, validation_service, orchestrator, registry


def _build_gated_service(store, validation_service, orchestrator, registry, audit_service=None):
    policy_service = LLMAgentPolicyService()
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    risk_assessor = LLMAgentPolicyRiskAssessor(enforcement, audit_service=audit_service, tool_registry=registry)
    gate = LLMAgentRiskApprovalGate()

    service = LLMAgentRiskGatedExecutionService(
        store, validation_service, orchestrator, enforcement,
        scope_for_plan=lambda plan_id: "notebook-1",
        risk_assessor=risk_assessor, approval_gate=gate,
    )
    return service, gate


def test_execution_boundary_low_risk_runs_immediately():
    call_count = {"calls": 0}
    store, validation_service, orchestrator, registry = _harness("lookup", call_count)
    store.add(_plan("plan-1", "lookup"))
    service, gate = _build_gated_service(store, validation_service, orchestrator, registry)

    result = service.execute_step("plan-1", "step-1", "user:ada")

    assert result.status == SUCCEEDED
    assert call_count["calls"] == 1


def test_execution_boundary_pauses_high_risk_until_approved():
    from backend.agent_policy_audit import LLMAgentPolicyAuditService

    call_count = {"calls": 0}
    store, validation_service, orchestrator, registry = _harness("lookup", call_count)
    store.add(_plan("plan-1", "lookup"))

    # four prior denied actions on record for this scope pushes the
    # score to HIGH (4 * 15 == 60) without touching the tool's own
    # registration/enabled state, so real execution can still succeed
    # once approved.
    audit_service = LLMAgentPolicyAuditService()
    policy_service = LLMAgentPolicyService()
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    denied = LLMAgentPolicyDecisionEngine().decide(
        {"scope_id": "notebook-1", "tool_name": "delete"}, resolver.resolve("notebook-1")
    )
    for i in range(4):
        audit_service.record("notebook-1", f"exec-{i}", denied)

    service, gate = _build_gated_service(store, validation_service, orchestrator, registry, audit_service)

    first = service.execute_step("plan-1", "step-1", "user:ada")
    assert first.status == DENIED
    assert "pending approval" in first.error
    assert call_count["calls"] == 0

    pending = gate.store.list_for_scope("notebook-1")
    assert len(pending) == 1
    request_id = pending[0].request_id

    gate.approve(request_id, "reviewer:ada")

    second = service.execute_step("plan-1", "step-1", "user:ada")
    assert second.status == SUCCEEDED
    assert call_count["calls"] == 1


def test_execution_boundary_stays_blocked_after_rejection():
    from backend.agent_policy_audit import LLMAgentPolicyAuditService

    call_count = {"calls": 0}
    store, validation_service, orchestrator, registry = _harness("lookup", call_count)
    store.add(_plan("plan-1", "lookup"))

    audit_service = LLMAgentPolicyAuditService()
    policy_service = LLMAgentPolicyService()
    resolver = LLMAgentPolicyResolver(policy_service)
    denied = LLMAgentPolicyDecisionEngine().decide(
        {"scope_id": "notebook-1", "tool_name": "delete"}, resolver.resolve("notebook-1")
    )
    for i in range(4):
        audit_service.record("notebook-1", f"exec-{i}", denied)

    service, gate = _build_gated_service(store, validation_service, orchestrator, registry, audit_service)

    service.execute_step("plan-1", "step-1", "user:ada")
    request_id = gate.store.list_for_scope("notebook-1")[0].request_id
    gate.reject(request_id, "reviewer:ada", "not approved for this notebook")

    result = service.execute_step("plan-1", "step-1", "user:ada")
    assert result.status == DENIED
    assert call_count["calls"] == 0


def test_execution_boundary_deny_never_reaches_approval_bypass():
    call_count = {"calls": 0}
    store, validation_service, orchestrator, registry = _harness("delete", call_count)
    store.add(_plan("plan-1", "delete"))

    policy_service = LLMAgentPolicyService()
    policy_service.create("notebook-1", "deny-policy", [_rule("deny-delete", POLICY_DENY, {"tool_name": "delete"})])
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    risk_assessor = LLMAgentPolicyRiskAssessor(enforcement, tool_registry=registry)
    gate = LLMAgentRiskApprovalGate()

    service = LLMAgentRiskGatedExecutionService(
        store, validation_service, orchestrator, enforcement,
        scope_for_plan=lambda plan_id: "notebook-1",
        risk_assessor=risk_assessor, approval_gate=gate,
    )

    result = service.execute_step("plan-1", "step-1", "user:ada")
    assert result.status == DENIED
    assert call_count["calls"] == 0

    # the deny was auto-rejected, never left REQUIRED for a human to approve
    scoped = gate.store.list_for_scope("notebook-1")
    assert len(scoped) == 1
    assert scoped[0].status == REJECTED
    with pytest.raises(InvalidApprovalTransitionError):
        gate.approve(scoped[0].request_id, "reviewer:ada")
