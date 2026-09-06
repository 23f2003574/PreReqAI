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
    APPROVED as APPROVAL_APPROVED,
)
from backend.agent_policy_risk_approval import (
    REJECTED as APPROVAL_REJECTED,
)
from backend.agent_policy_risk_approval import (
    LLMAgentRiskApprovalGate,
    LLMAgentRiskGatedExecutionService,
)
from backend.agent_policy_risk_assessment import LEVEL_HIGH, LLMAgentPolicyRiskAssessor
from backend.agent_policy_risk_classification import LLMAgentPolicyRiskClassifier, RiskClassification
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine
from backend.agent_policy_risk_review_assignment import LLMAgentRiskReviewAssignment
from backend.agent_policy_risk_review_queue import ExpiredReviewItemError, LLMAgentRiskReviewQueue
from backend.agent_policy_risk_review_resolution import (
    AlreadyResolvedError,
    CannotApproveDeniedActionError,
    LLMAgentRiskReviewResolver,
    ReviewNotClaimedError,
    ReviewResolution,
    UnauthorizedReviewerError,
)
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

ACTION_CONTEXT = {"scope_id": "notebook-1", "plan_id": "plan-1", "step_id": "step-1", "tool_name": "delete", "arguments": {}}


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _classification(risk_level, risk_factors=None):
    return RiskClassification(
        risk_level=risk_level, confidence="HIGH", evidence={}, risk_factors=risk_factors or {},
        reasons=["synthetic"], provenance={},
    )


def _review_decision(scope_id="notebook-1"):
    context = {**ACTION_CONTEXT, "scope_id": scope_id}
    return LLMAgentPolicyRiskDecisionEngine().decide(context, _classification(LEVEL_HIGH, {"prior_denied_actions": 4})), context


def _setup():
    gate = LLMAgentRiskApprovalGate()
    queue = LLMAgentRiskReviewQueue(gate)
    resolver = LLMAgentRiskReviewResolver(queue)
    return gate, queue, resolver


def _claimed_item(queue, reviewer="reviewer:ada", scope_id="notebook-1"):
    decision, context = _review_decision(scope_id)
    item = queue.enqueue(decision, context)
    return queue.claim(item.item_id, reviewer)


# --- approve review -----------------------------------------------------------


def test_approve_review():
    gate, queue, resolver = _setup()
    item = _claimed_item(queue)

    resolution = resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:ada")

    assert isinstance(resolution, ReviewResolution)
    assert resolution.outcome == APPROVAL_APPROVED
    assert resolution.reviewer == "reviewer:ada"
    assert gate.get(item.approval_request_id).status == APPROVAL_APPROVED


# --- reject review -----------------------------------------------------------


def test_reject_review():
    gate, queue, resolver = _setup()
    item = _claimed_item(queue)

    resolution = resolver.resolve(item.item_id, APPROVAL_REJECTED, "reviewer:ada", reason="too risky")

    assert resolution.outcome == APPROVAL_REJECTED
    assert resolution.reason == "too risky"
    assert gate.get(item.approval_request_id).status == APPROVAL_REJECTED


def test_reject_requires_a_reason():
    gate, queue, resolver = _setup()
    item = _claimed_item(queue)
    with pytest.raises(ValueError):
        resolver.resolve(item.item_id, APPROVAL_REJECTED, "reviewer:ada")


# --- unauthorized reviewer ----------------------------------------------------


def test_unauthorized_reviewer_cannot_resolve():
    gate, queue, resolver = _setup()
    item = _claimed_item(queue, reviewer="reviewer:ada")

    with pytest.raises(UnauthorizedReviewerError):
        resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:mallory")

    # nothing was applied by the rejected attempt
    assert gate.get(item.approval_request_id).status not in (APPROVAL_APPROVED, APPROVAL_REJECTED)


def test_authorized_reviewer_is_the_active_assignment_when_configured():
    gate = LLMAgentRiskApprovalGate()
    queue = LLMAgentRiskReviewQueue(gate)
    assignment_service = LLMAgentRiskReviewAssignment(queue, lambda reviewer, scope_id: True)
    resolver = LLMAgentRiskReviewResolver(queue, assignment_service)

    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    queue.claim(item.item_id, "reviewer:ada")  # claimed directly, bypassing assignment
    assignment_service.assign(item.item_id, "reviewer:bob")  # but bob never got the real claim (conflict)

    # bob holds the active Assignment even though ada still holds the
    # real queue-level claim; the assignment is authoritative here
    with pytest.raises(UnauthorizedReviewerError):
        resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:ada")

    resolution = resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:bob")
    assert resolution.reviewer == "reviewer:bob"


def test_cannot_resolve_an_unclaimed_item():
    gate, queue, resolver = _setup()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)

    with pytest.raises(ReviewNotClaimedError):
        resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:ada")


# --- expired item ----------------------------------------------------------------


def test_expired_item_cannot_be_resolved():
    gate = LLMAgentRiskApprovalGate(approval_window=timedelta(seconds=-1))
    queue = LLMAgentRiskReviewQueue(gate)
    resolver = LLMAgentRiskReviewResolver(queue)
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)

    with pytest.raises(ExpiredReviewItemError):
        resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:ada")


# --- already resolved --------------------------------------------------------------


def test_already_resolved_with_a_different_outcome_raises():
    gate, queue, resolver = _setup()
    item = _claimed_item(queue)
    resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:ada")

    with pytest.raises(AlreadyResolvedError):
        resolver.resolve(item.item_id, APPROVAL_REJECTED, "reviewer:ada", reason="changed my mind")


def test_already_resolved_by_a_different_reviewer_raises():
    gate, queue, resolver = _setup()
    item = _claimed_item(queue)
    resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:ada")

    with pytest.raises(AlreadyResolvedError):
        resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:bob")


# --- duplicate resolution -----------------------------------------------------------


def test_duplicate_resolution_is_idempotent():
    gate, queue, resolver = _setup()
    item = _claimed_item(queue)

    first = resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:ada")
    second = resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:ada")

    assert first == second


def test_duplicate_rejection_with_the_same_reason_is_idempotent():
    gate, queue, resolver = _setup()
    item = _claimed_item(queue)

    first = resolver.resolve(item.item_id, APPROVAL_REJECTED, "reviewer:ada", reason="too risky")
    second = resolver.resolve(item.item_id, APPROVAL_REJECTED, "reviewer:ada", reason="too risky")

    assert first == second


# --- policy deny cannot be approved --------------------------------------------------


def test_policy_denial_cannot_be_approved_even_if_it_reached_the_queue():
    # defense in depth: even a hand-corrupted item whose decision
    # carries a real policy_denial factor can never be approved.
    from dataclasses import replace as dc_replace

    gate, queue, resolver = _setup()
    item = _claimed_item(queue)

    corrupted_decision = dc_replace(
        item.decision, risk_factors={**item.decision.risk_factors, "policy_denial": 1}
    )
    corrupted = dc_replace(item, decision=corrupted_decision)
    queue.store.save(corrupted)

    with pytest.raises(CannotApproveDeniedActionError):
        resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:ada")


# --- provenance ----------------------------------------------------------------------


def test_provenance_preserves_reviewer_reason_evidence_and_review_item():
    gate, queue, resolver = _setup()
    item = _claimed_item(queue)

    resolution = resolver.resolve(item.item_id, APPROVAL_REJECTED, "reviewer:ada", reason="too risky")

    assert resolution.provenance["item_id"] == item.item_id
    assert resolution.provenance["decision"] == item.decision
    assert resolution.provenance["review_item"].item_id == item.item_id
    assert resolution.decision.risk_level == LEVEL_HIGH
    assert resolution.decision.risk_factors == {"prior_denied_actions": 4}
    assert resolution.approval_request_id == item.approval_request_id


# --- enforcement sees resolution ------------------------------------------------------


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
    registry.register(tool_name, f"Tool {tool_name}", {"type": "object", "properties": {}, "required": []})

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


def test_enforcement_sees_resolution_end_to_end():
    from backend.agent_policy_audit import LLMAgentPolicyAuditService

    call_count = {"calls": 0}
    store, validation_service, orchestrator, registry = _harness("lookup", call_count)
    store.add(_plan("plan-1", "lookup"))

    audit_service = LLMAgentPolicyAuditService()
    policy_service = LLMAgentPolicyService()
    resolver_svc = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver_svc, LLMAgentPolicyDecisionEngine())
    denied = LLMAgentPolicyDecisionEngine().decide(
        {"scope_id": "notebook-1", "tool_name": "delete"}, resolver_svc.resolve("notebook-1")
    )
    for i in range(4):
        audit_service.record("notebook-1", f"exec-{i}", denied)

    risk_assessor = LLMAgentPolicyRiskAssessor(enforcement, audit_service=audit_service, tool_registry=registry)
    gate = LLMAgentRiskApprovalGate()
    queue = LLMAgentRiskReviewQueue(gate)
    review_resolver = LLMAgentRiskReviewResolver(queue)

    execution_service = LLMAgentRiskGatedExecutionService(
        store, validation_service, orchestrator, enforcement,
        scope_for_plan=lambda plan_id: "notebook-1",
        risk_assessor=risk_assessor, approval_gate=gate,
    )

    first = execution_service.execute_step("plan-1", "step-1", "user:ada")
    assert first.status == DENIED
    assert call_count["calls"] == 0

    # recompute the same (deterministic) decision independently, the
    # way an out-of-band reviewer surface would -- using the exact same
    # action_context shape LLMAgentRiskGatedExecutionService.execute_step()
    # itself builds, so this reaches the identical, already-idempotent
    # Commit #5 request_id -- and enqueue/claim/resolve it entirely
    # through Commits #8-#10
    real_action_context = {
        "scope_id": "notebook-1", "plan_id": "plan-1", "step_id": "step-1",
        "tool_name": "lookup", "arguments": {}, "subject": "user:ada",
    }
    classification = LLMAgentPolicyRiskClassifier().classify(risk_assessor.assess(real_action_context))
    decision = LLMAgentPolicyRiskDecisionEngine().decide(real_action_context, classification)
    item = queue.enqueue(decision, real_action_context)
    queue.claim(item.item_id, "reviewer:ada")
    review_resolver.resolve(item.item_id, APPROVAL_APPROVED, "reviewer:ada")

    second = execution_service.execute_step("plan-1", "step-1", "user:ada")
    assert second.status == SUCCEEDED
    assert call_count["calls"] == 1
