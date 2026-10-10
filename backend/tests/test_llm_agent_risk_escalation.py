from datetime import timedelta

import pytest

from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
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
)
from backend.agent_policy_risk_assessment import LEVEL_HIGH, LLMAgentPolicyRiskAssessor
from backend.agent_policy_risk_classification import LLMAgentPolicyRiskClassifier, RiskClassification
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine
from backend.agent_policy_risk_escalation import (
    APPROVED,
    EXPIRED,
    PENDING,
    REJECTED,
    Escalation,
    EscalationNotAllowedError,
    ExpiredEscalationError,
    InvalidEscalationTransitionError,
    LLMAgentRiskEscalationService,
    ScopeMismatchError,
    UnknownEscalationError,
)

ACTION_CONTEXT = {"scope_id": "notebook-1", "plan_id": "plan-1", "step_id": "step-1", "tool_name": "delete", "arguments": {}}


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _review_decision(scope_id="notebook-1"):
    classification = RiskClassification(
        risk_level=LEVEL_HIGH, confidence="HIGH", evidence={}, risk_factors={"prior_denied_actions": 4},
        reasons=["synthetic high risk"], provenance={},
    )
    context = {**ACTION_CONTEXT, "scope_id": scope_id}
    return LLMAgentPolicyRiskDecisionEngine().decide(context, classification), context


def _deny_decision():
    policy_service = LLMAgentPolicyService()
    policy_service.create("notebook-1", "deny-policy", [_rule("deny-delete", POLICY_DENY, {"tool_name": "delete"})])
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    assessment = LLMAgentPolicyRiskAssessor(enforcement).assess(ACTION_CONTEXT)
    classification = LLMAgentPolicyRiskClassifier().classify(assessment)
    return LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification)


def _pending_escalation(gate=None, escalation_service=None, scope_id="notebook-1"):
    gate = gate or LLMAgentRiskApprovalGate()
    service = escalation_service or LLMAgentRiskEscalationService(gate)
    decision, context = _review_decision(scope_id)
    requirement = gate.evaluate(decision, context)
    escalation = service.escalate(requirement.request_id, "needs a second pair of eyes")
    return gate, service, escalation


# --- escalation creation -----------------------------------------------------


def test_escalation_creation():
    gate, service, escalation = _pending_escalation()

    assert isinstance(escalation, Escalation)
    assert escalation.status == PENDING
    assert escalation.reason == "needs a second pair of eyes"
    assert escalation.scope_id == "notebook-1"
    assert escalation.actor is None
    assert escalation.expires_at is not None


def test_only_required_actions_can_escalate():
    gate = LLMAgentRiskApprovalGate()
    service = LLMAgentRiskEscalationService(gate)
    decision, context = _review_decision()
    requirement = gate.evaluate(decision, context)
    gate.approve(requirement.request_id, "reviewer:ada")  # now APPROVED, not REQUIRED

    with pytest.raises(EscalationNotAllowedError):
        service.escalate(requirement.request_id, "too late")


def test_cannot_escalate_the_same_request_twice_while_pending():
    gate, service, escalation = _pending_escalation()

    with pytest.raises(EscalationNotAllowedError):
        service.escalate(escalation.request_id, "again")


# --- approval resolution -------------------------------------------------------


def test_approval_resolution_drives_the_underlying_gate():
    gate, service, escalation = _pending_escalation()

    resolved = service.resolve(escalation.escalation_id, APPROVED, "senior:ada")

    assert resolved.status == APPROVED
    assert resolved.actor == "senior:ada"
    assert resolved.resolved_at is not None

    requirement = gate.get(escalation.request_id)
    assert requirement.status == APPROVAL_APPROVED
    assert requirement.actor == "senior:ada"


# --- rejection resolution -------------------------------------------------------


def test_rejection_resolution_drives_the_underlying_gate():
    gate, service, escalation = _pending_escalation()

    resolved = service.resolve(escalation.escalation_id, REJECTED, "senior:ada", resolution_reason="too risky")

    assert resolved.status == REJECTED

    requirement = gate.get(escalation.request_id)
    assert requirement.status == APPROVAL_REJECTED
    assert requirement.reason == "too risky"


def test_rejection_requires_a_resolution_reason():
    gate, service, escalation = _pending_escalation()
    with pytest.raises(ValueError):
        service.resolve(escalation.escalation_id, REJECTED, "senior:ada")


def test_resolving_an_already_resolved_escalation_raises():
    gate, service, escalation = _pending_escalation()
    service.resolve(escalation.escalation_id, APPROVED, "senior:ada")

    with pytest.raises(InvalidEscalationTransitionError):
        service.resolve(escalation.escalation_id, APPROVED, "senior:bob")


# --- expired escalation -----------------------------------------------------------


def test_expired_escalation_cannot_authorize_execution():
    gate = LLMAgentRiskApprovalGate()
    service = LLMAgentRiskEscalationService(gate, escalation_window=timedelta(seconds=-1))
    gate2, _, escalation = _pending_escalation(gate=gate, escalation_service=service)

    assert service.get(escalation.escalation_id).status == EXPIRED

    with pytest.raises(ExpiredEscalationError):
        service.resolve(escalation.escalation_id, APPROVED, "senior:ada")

    # the underlying requirement was never touched by the failed attempt
    assert gate.get(escalation.request_id).status not in (APPROVAL_APPROVED,)


def test_a_fresh_escalation_can_be_raised_after_expiry():
    gate = LLMAgentRiskApprovalGate()
    service = LLMAgentRiskEscalationService(gate, escalation_window=timedelta(seconds=-1))
    gate2, _, stale = _pending_escalation(gate=gate, escalation_service=service)

    fresh = service.escalate(stale.request_id, "still needs review")
    assert fresh.escalation_id != stale.escalation_id
    assert fresh.status == PENDING


def test_unknown_escalation_id_raises():
    service = LLMAgentRiskEscalationService(LLMAgentRiskApprovalGate())
    with pytest.raises(UnknownEscalationError):
        service.get("does-not-exist")
    with pytest.raises(UnknownEscalationError):
        service.resolve("does-not-exist", APPROVED, "senior:ada")


# --- policy-denied action -------------------------------------------------------


def test_policy_denied_action_cannot_be_escalated():
    gate = LLMAgentRiskApprovalGate()
    service = LLMAgentRiskEscalationService(gate)
    requirement = gate.evaluate(_deny_decision(), ACTION_CONTEXT)  # auto-REJECTED, never REQUIRED

    with pytest.raises(EscalationNotAllowedError):
        service.escalate(requirement.request_id, "please reconsider")


def test_escalation_cannot_approve_a_corrupted_denied_decision():
    # defense in depth: even if an escalation somehow carries a decision
    # whose risk_factors show a real policy denial, resolve() must never
    # approve it into execution.
    gate = LLMAgentRiskApprovalGate()
    service = LLMAgentRiskEscalationService(gate)
    decision, context = _review_decision()
    requirement = gate.evaluate(decision, context)
    escalation = service.escalate(requirement.request_id, "reviewing")

    # hand-corrupt the stored escalation's decision to carry a policy_denial factor
    from dataclasses import replace as dc_replace

    corrupted_decision = dc_replace(decision, risk_factors={**decision.risk_factors, "policy_denial": 1})
    corrupted = dc_replace(escalation, decision=corrupted_decision)
    service.store.save(corrupted)

    with pytest.raises(InvalidEscalationTransitionError):
        service.resolve(escalation.escalation_id, APPROVED, "senior:ada")


# --- invalid actor/scope -----------------------------------------------------------


def test_resolve_requires_a_non_blank_actor():
    gate, service, escalation = _pending_escalation()
    with pytest.raises(ValueError):
        service.resolve(escalation.escalation_id, APPROVED, "")
    with pytest.raises(ValueError):
        service.resolve(escalation.escalation_id, APPROVED, None)


def test_resolve_rejects_a_mismatched_scope():
    gate, service, escalation = _pending_escalation(scope_id="notebook-1")

    with pytest.raises(ScopeMismatchError):
        service.resolve(escalation.escalation_id, APPROVED, "senior:ada", scope_id="notebook-other")

    # a matching scope_id succeeds
    resolved = service.resolve(escalation.escalation_id, APPROVED, "senior:ada", scope_id="notebook-1")
    assert resolved.status == APPROVED


def test_escalate_requires_non_blank_request_id_and_reason():
    service = LLMAgentRiskEscalationService(LLMAgentRiskApprovalGate())
    with pytest.raises(ValueError):
        service.escalate("", "reason")
    with pytest.raises(ValueError):
        service.escalate("some-id", "")


# --- provenance ----------------------------------------------------------------


def test_provenance_carries_forward_decision_and_context():
    gate, service, escalation = _pending_escalation()

    assert escalation.provenance["request_id"] == escalation.request_id
    assert escalation.provenance["decision"] == escalation.decision
    assert escalation.provenance["action_context"] == escalation.action_context
    assert escalation.decision.risk_level == LEVEL_HIGH
    assert escalation.decision.risk_factors == {"prior_denied_actions": 4}


# --- integration with approval gate --------------------------------------------


def test_integration_approving_escalation_lets_a_retry_proceed():
    gate = LLMAgentRiskApprovalGate()
    service = LLMAgentRiskEscalationService(gate)
    decision, context = _review_decision()

    requirement = gate.evaluate(decision, context)
    escalation = service.escalate(requirement.request_id, "escalating for senior review")
    service.resolve(escalation.escalation_id, APPROVED, "senior:ada")

    # a retried evaluate() for the identical action/context now reaches
    # the same, now-approved requirement -- exactly the mechanism
    # LLMAgentRiskGatedExecutionService relies on for a retried
    # execute_step() to proceed, with zero changes to Commit #5 itself
    retried = gate.evaluate(decision, context)
    assert retried.request_id == requirement.request_id
    assert retried.status == APPROVAL_APPROVED
    assert retried.actor == "senior:ada"


def test_integration_rejecting_escalation_keeps_a_retry_blocked():
    gate = LLMAgentRiskApprovalGate()
    service = LLMAgentRiskEscalationService(gate)
    decision, context = _review_decision()

    requirement = gate.evaluate(decision, context)
    escalation = service.escalate(requirement.request_id, "escalating for senior review")
    service.resolve(escalation.escalation_id, REJECTED, "senior:ada", resolution_reason="denied on review")

    retried = gate.evaluate(decision, context)
    assert retried.status == APPROVAL_REJECTED
