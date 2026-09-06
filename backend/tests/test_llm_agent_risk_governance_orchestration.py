from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_policy_audit import LLMAgentPolicyAuditService
from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
from backend.agent_policy_engine import ALLOW as POLICY_ALLOW
from backend.agent_policy_engine import DENY as POLICY_DENY
from backend.agent_policy_engine import LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcedExecutionService, LLMAgentPolicyEnforcement
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_policy_risk_approval import APPROVED, REJECTED, LLMAgentRiskApprovalGate
from backend.agent_policy_risk_assessment import (
    LEVEL_CRITICAL,
    LEVEL_HIGH,
    LEVEL_LOW,
    InvalidActionContextError,
    LLMAgentPolicyRiskAssessor,
)
from backend.agent_policy_risk_review_queue import CLAIMED, PENDING, LLMAgentRiskReviewQueue
from backend.agent_policy_risk_review_resolution import LLMAgentRiskReviewResolver
from backend.agent_risk_governance import LLMAgentRiskGovernanceOrchestrator, RiskGovernanceResult
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

SCHEMA = {"type": "object", "properties": {}, "required": []}


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


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


def _plan(plan_id, tool_name, step_id="step-1"):
    return LLMAgentPlan(
        plan_id=plan_id, task="a test task", steps=[_step(step_id, tool_name)],
        status=READY, created_at=datetime.now(timezone.utc),
    )


def _harness(tool_names, call_count):
    if isinstance(tool_names, str):
        tool_names = [tool_names]

    store = MultiPlanStore()
    registry = LLMToolRegistryService()

    def handler():
        call_count["calls"] += 1
        return {"found": True}

    execution = None
    permissions = None
    invocation = None
    for tool_name in tool_names:
        registry.register(tool_name, f"Tool {tool_name}", SCHEMA)
        if invocation is None:
            invocation = LLMToolInvocationService(registry)
            permissions = LLMToolPermissionService(registry, invocation)
            execution = LLMToolExecutionService(registry, permissions)
        permissions.register(
            LLMToolPermissionPolicy(policy_id=f"allow-{tool_name}", tool_name=tool_name, subject=ANY_SUBJECT, allowed=True)
        )
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


def _build(tool_name, call_count, scope_id="notebook-1", audit_service=None, with_execution=True):
    store, validation_service, orchestrator, registry = _harness(tool_name, call_count)
    store.add(_plan("plan-1", tool_name))

    policy_service = LLMAgentPolicyService()
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())

    risk_assessor = LLMAgentPolicyRiskAssessor(enforcement, audit_service=audit_service, tool_registry=registry)
    gate = LLMAgentRiskApprovalGate()
    queue = LLMAgentRiskReviewQueue(gate)

    execution_service = None
    if with_execution:
        execution_service = LLMAgentPolicyEnforcedExecutionService(
            store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: scope_id
        )

    governance = LLMAgentRiskGovernanceOrchestrator(
        risk_assessor, queue, execution_service=execution_service
    )
    return governance, queue, gate, policy_service, resolver, enforcement, call_count


def _action_context(scope_id, tool_name, step_id="step-1"):
    return {
        "scope_id": scope_id, "plan_id": "plan-1", "step_id": step_id,
        "tool_name": tool_name, "arguments": {}, "subject": "user:ada",
    }


def _four_prior_denials(audit_service, scope_id, resolver):
    denied = LLMAgentPolicyDecisionEngine().decide(
        {"scope_id": scope_id, "tool_name": "delete"}, resolver.resolve(scope_id)
    )
    for i in range(4):
        audit_service.record(scope_id, f"exec-{i}", denied)


# --- low-risk allow -------------------------------------------------------------


def test_low_risk_allow():
    call_count = {"calls": 0}
    governance, queue, gate, policy_service, resolver, enforcement, call_count = _build("lookup", call_count)

    result = governance.evaluate(_action_context("notebook-1", "lookup"))

    assert isinstance(result, RiskGovernanceResult)
    assert result.final_decision == POLICY_ALLOW
    assert result.assessment.risk_level == LEVEL_LOW
    assert result.review_item is None
    assert result.executed.status == SUCCEEDED
    assert call_count["calls"] == 1


def test_evaluate_without_execution_service_never_executes():
    call_count = {"calls": 0}
    governance, queue, gate, policy_service, resolver, enforcement, call_count = _build(
        "lookup", call_count, with_execution=False
    )

    result = governance.evaluate(_action_context("notebook-1", "lookup"))

    assert result.final_decision == POLICY_ALLOW
    assert result.executed is None
    assert call_count["calls"] == 0


# --- high-risk deny (real policy denial) ----------------------------------------


def test_high_risk_deny_via_policy():
    call_count = {"calls": 0}
    governance, queue, gate, policy_service, resolver, enforcement, call_count = _build("delete", call_count)
    policy_service.create("notebook-1", "deny-policy", [_rule("deny-delete", POLICY_DENY, {"tool_name": "delete"})])

    result = governance.evaluate(_action_context("notebook-1", "delete"))

    assert result.final_decision == POLICY_DENY
    assert result.assessment.risk_level == LEVEL_CRITICAL
    assert result.executed is None
    assert call_count["calls"] == 0


# --- review queue flow ---------------------------------------------------------


def test_review_queue_flow_enqueues_a_pending_item():
    call_count = {"calls": 0}
    audit_service = LLMAgentPolicyAuditService()
    governance, queue, gate, policy_service, resolver, enforcement, call_count = _build(
        "lookup", call_count, audit_service=audit_service
    )
    _four_prior_denials(audit_service, "notebook-1", resolver)

    result = governance.evaluate(_action_context("notebook-1", "lookup"))

    assert result.final_decision == "REVIEW"
    assert result.review_item is not None
    assert result.review_item.status == PENDING
    assert result.executed is None
    assert call_count["calls"] == 0

    scoped = queue.list("notebook-1")
    assert len(scoped) == 1
    assert scoped[0].item_id == result.review_item.item_id


# --- approved review executes ---------------------------------------------------


def test_approved_review_executes_on_retry():
    call_count = {"calls": 0}
    audit_service = LLMAgentPolicyAuditService()
    governance, queue, gate, policy_service, resolver, enforcement, call_count = _build(
        "lookup", call_count, audit_service=audit_service
    )
    _four_prior_denials(audit_service, "notebook-1", resolver)

    first = governance.evaluate(_action_context("notebook-1", "lookup"))
    assert first.final_decision == "REVIEW"

    queue.claim(first.review_item.item_id, "reviewer:ada")
    review_resolver = LLMAgentRiskReviewResolver(queue)
    review_resolver.resolve(first.review_item.item_id, APPROVED, "reviewer:ada")

    second = governance.evaluate(_action_context("notebook-1", "lookup"))

    assert second.final_decision == POLICY_ALLOW
    assert second.review_item.status == "RESOLVED"
    assert second.executed.status == SUCCEEDED
    assert call_count["calls"] == 1


# --- rejected/expired review blocks -----------------------------------------------


def test_rejected_review_blocks_permanently():
    call_count = {"calls": 0}
    audit_service = LLMAgentPolicyAuditService()
    governance, queue, gate, policy_service, resolver, enforcement, call_count = _build(
        "lookup", call_count, audit_service=audit_service
    )
    _four_prior_denials(audit_service, "notebook-1", resolver)

    first = governance.evaluate(_action_context("notebook-1", "lookup"))
    queue.claim(first.review_item.item_id, "reviewer:ada")
    review_resolver = LLMAgentRiskReviewResolver(queue)
    review_resolver.resolve(first.review_item.item_id, REJECTED, "reviewer:ada", reason="too risky")

    second = governance.evaluate(_action_context("notebook-1", "lookup"))

    assert second.final_decision == POLICY_DENY
    assert any("rejected" in reason for reason in second.reasons)
    assert second.executed is None
    assert call_count["calls"] == 0


def test_expired_review_blocks():
    call_count = {"calls": 0}
    audit_service = LLMAgentPolicyAuditService()
    store, validation_service, orchestrator, registry = _harness("lookup", call_count)
    store.add(_plan("plan-1", "lookup"))
    policy_service = LLMAgentPolicyService()
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    risk_assessor = LLMAgentPolicyRiskAssessor(enforcement, audit_service=audit_service, tool_registry=registry)
    _four_prior_denials(audit_service, "notebook-1", resolver)

    gate = LLMAgentRiskApprovalGate(approval_window=timedelta(seconds=-1))
    queue = LLMAgentRiskReviewQueue(gate)
    execution_service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )
    governance = LLMAgentRiskGovernanceOrchestrator(risk_assessor, queue, execution_service=execution_service)

    result = governance.evaluate(_action_context("notebook-1", "lookup"))

    assert result.final_decision == POLICY_DENY
    assert any("expired" in reason for reason in result.reasons)
    assert call_count["calls"] == 0


# --- policy deny precedence -------------------------------------------------------


def test_policy_deny_precedence_over_lenient_thresholds():
    from backend.agent_policy_risk_thresholds import LLMAgentPolicyRiskThresholdService, RiskThresholds

    call_count = {"calls": 0}
    store, validation_service, orchestrator, registry = _harness("delete", call_count)
    store.add(_plan("plan-1", "delete"))
    policy_service = LLMAgentPolicyService()
    policy_service.create("notebook-1", "deny-policy", [_rule("deny-delete", POLICY_DENY, {"tool_name": "delete"})])
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    risk_assessor = LLMAgentPolicyRiskAssessor(enforcement, tool_registry=registry)

    threshold_service = LLMAgentPolicyRiskThresholdService()
    threshold_service.set(
        "notebook-1", RiskThresholds(scope_id="notebook-1", review_at=LEVEL_CRITICAL, deny_at=LEVEL_CRITICAL)
    )

    gate = LLMAgentRiskApprovalGate()
    queue = LLMAgentRiskReviewQueue(gate)
    execution_service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )
    governance = LLMAgentRiskGovernanceOrchestrator(
        risk_assessor, queue, threshold_service=threshold_service, execution_service=execution_service
    )

    result = governance.evaluate(_action_context("notebook-1", "delete"))

    assert result.final_decision == POLICY_DENY
    assert result.review_item is None
    assert call_count["calls"] == 0


# --- provenance propagation -----------------------------------------------------------


def test_provenance_propagation():
    call_count = {"calls": 0}
    governance, queue, gate, policy_service, resolver, enforcement, call_count = _build("lookup", call_count)

    result = governance.evaluate(_action_context("notebook-1", "lookup"))

    assert result.provenance["assessment"] is result.assessment
    assert result.provenance["classification"] is result.classification
    assert result.provenance["decision"] is result.decision
    assert result.provenance["action_context"] == _action_context("notebook-1", "lookup")
    assert result.provenance["review_item"] is None


def test_provenance_includes_review_item_when_enqueued():
    call_count = {"calls": 0}
    audit_service = LLMAgentPolicyAuditService()
    governance, queue, gate, policy_service, resolver, enforcement, call_count = _build(
        "lookup", call_count, audit_service=audit_service
    )
    _four_prior_denials(audit_service, "notebook-1", resolver)

    result = governance.evaluate(_action_context("notebook-1", "lookup"))

    assert result.provenance["review_item"] is result.review_item
    assert result.review_item.decision.risk_level == LEVEL_HIGH


# --- execution-boundary integration -----------------------------------------------------


def test_execution_boundary_integration_matches_direct_execution():
    call_count = {"calls": 0}
    governance, queue, gate, policy_service, resolver, enforcement, call_count = _build("lookup", call_count)

    result = governance.evaluate(_action_context("notebook-1", "lookup"))

    # the orchestrator's own executed result is the real
    # LLMAgentStepExecution the plain (non-risk) execution boundary
    # would itself produce -- reused, not reimplemented
    assert result.executed.plan_id == "plan-1"
    assert result.executed.step_id == "step-1"
    assert result.executed.status == SUCCEEDED
    assert result.executed.result is not None


def test_invalid_action_context_rejected():
    call_count = {"calls": 0}
    governance, queue, gate, policy_service, resolver, enforcement, call_count = _build("lookup", call_count)
    with pytest.raises(InvalidActionContextError):
        governance.evaluate("not-a-dict")


# --- regression coverage --------------------------------------------------------------------


def test_regression_full_lifecycle_end_to_end():
    """One consolidated pass through every branch this orchestrator can
    take, all against real Commit #1-#10 infrastructure and the real
    execution boundary -- a broad regression check that the composed
    pipeline still behaves correctly end-to-end, not just in isolated
    unit tests per commit."""
    # "fetch" (rather than reusing "lookup") is used for the review-flow
    # step so its post-approval retry is a genuinely fresh execution,
    # never served from the tool-calling pipeline's own idempotency
    # cache against step 1's already-succeeded "lookup" call.
    call_count = {"calls": 0}
    audit_service = LLMAgentPolicyAuditService()
    store, validation_service, orchestrator, registry = _harness(["lookup", "fetch"], call_count)
    store.add(_plan("plan-1", "lookup", step_id="step-1"))
    store.add(_plan("plan-2", "fetch", step_id="step-2"))
    store.add(_plan("plan-3", "delete", step_id="step-3"))

    registry.register("delete", "Deletes things", SCHEMA)
    policy_service = LLMAgentPolicyService()
    policy_service.create("notebook-1", "deny-policy", [_rule("deny-delete", POLICY_DENY, {"tool_name": "delete"})])
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    risk_assessor = LLMAgentPolicyRiskAssessor(enforcement, audit_service=audit_service, tool_registry=registry)
    gate = LLMAgentRiskApprovalGate()
    queue = LLMAgentRiskReviewQueue(gate)
    execution_service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )
    governance = LLMAgentRiskGovernanceOrchestrator(risk_assessor, queue, execution_service=execution_service)

    # 1. low risk -> allow, real execution succeeds
    low = governance.evaluate(_action_context("notebook-1", "lookup", step_id="step-1"))
    assert low.final_decision == POLICY_ALLOW and low.executed.status == SUCCEEDED

    # 2. explicit policy deny -> always denied, never executed, never reviewable
    denied = governance.evaluate({**_action_context("notebook-1", "delete", step_id="step-3"), "plan_id": "plan-3"})
    assert denied.final_decision == POLICY_DENY and denied.review_item is None
    assert call_count["calls"] == 1  # unchanged since step 1

    # 3. push risk high via history, triggering review, then approve and retry
    _four_prior_denials(audit_service, "notebook-1", resolver)
    review_context = {**_action_context("notebook-1", "fetch", step_id="step-2"), "plan_id": "plan-2"}
    pending = governance.evaluate(review_context)
    assert pending.final_decision == "REVIEW"

    queue.claim(pending.review_item.item_id, "reviewer:ada")
    LLMAgentRiskReviewResolver(queue).resolve(pending.review_item.item_id, APPROVED, "reviewer:ada")

    approved = governance.evaluate(review_context)
    assert approved.final_decision == POLICY_ALLOW
    assert approved.executed.status == SUCCEEDED
    assert call_count["calls"] == 2
