from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_risk_approval import (
    APPROVED as APPROVAL_APPROVED,
)
from backend.agent_policy_risk_approval import (
    EXPIRED as APPROVAL_EXPIRED,
)
from backend.agent_policy_risk_approval import (
    REQUIRED as APPROVAL_REQUIRED,
)
from backend.agent_policy_risk_approval import (
    ExpiredApprovalError,
    InMemoryApprovalRequirementStore,
    LLMAgentRiskApprovalGate,
)
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine
from backend.agent_policy_risk_escalation import (
    APPROVED as ESCALATION_APPROVED,
)
from backend.agent_policy_risk_escalation import (
    EXPIRED as ESCALATION_EXPIRED,
)
from backend.agent_policy_risk_escalation import (
    PENDING as ESCALATION_PENDING,
)
from backend.agent_policy_risk_escalation import (
    ExpiredEscalationError,
    InMemoryEscalationStore,
    LLMAgentRiskEscalationService,
)
from backend.agent_policy_risk_expiration import InvalidExpirationTargetError, LLMAgentRiskExpirationService
from backend.agent_policy_risk_assessment import LEVEL_HIGH
from backend.agent_policy_risk_classification import RiskClassification

ACTION_CONTEXT = {"scope_id": "notebook-1", "plan_id": "plan-1", "step_id": "step-1", "tool_name": "delete", "arguments": {}}


def _review_decision(scope_id="notebook-1"):
    classification = RiskClassification(
        risk_level=LEVEL_HIGH, confidence="HIGH", evidence={}, risk_factors={"prior_denied_actions": 4},
        reasons=["synthetic high risk"], provenance={},
    )
    context = {**ACTION_CONTEXT, "scope_id": scope_id}
    return LLMAgentPolicyRiskDecisionEngine().decide(context, classification), context


def _required_requirement(gate, scope_id="notebook-1"):
    decision, context = _review_decision(scope_id)
    return gate.evaluate(decision, context)


def _pending_escalation(gate, escalation_service, scope_id="notebook-1"):
    requirement = _required_requirement(gate, scope_id)
    return escalation_service.escalate(requirement.request_id, "needs review")


# --- before expiry -----------------------------------------------------------


def test_before_expiry_is_not_expired():
    store = InMemoryApprovalRequirementStore()
    gate = LLMAgentRiskApprovalGate(store=store)
    requirement = _required_requirement(gate)

    expiration = LLMAgentRiskExpirationService(store)
    just_before = requirement.expires_at - timedelta(seconds=1)

    assert expiration.is_expired(requirement, just_before) is False


# --- exact expiry boundary -----------------------------------------------------


def test_exact_expiry_boundary_is_expired():
    store = InMemoryApprovalRequirementStore()
    gate = LLMAgentRiskApprovalGate(store=store)
    requirement = _required_requirement(gate)

    expiration = LLMAgentRiskExpirationService(store)

    assert expiration.is_expired(requirement, requirement.expires_at) is True


# --- after expiry --------------------------------------------------------------


def test_after_expiry_is_expired():
    store = InMemoryApprovalRequirementStore()
    gate = LLMAgentRiskApprovalGate(store=store)
    requirement = _required_requirement(gate)

    expiration = LLMAgentRiskExpirationService(store)
    well_after = requirement.expires_at + timedelta(days=1)

    assert expiration.is_expired(requirement, well_after) is True


def test_escalation_expiry_before_exact_and_after():
    approval_store = InMemoryApprovalRequirementStore()
    escalation_store = InMemoryEscalationStore()
    gate = LLMAgentRiskApprovalGate(store=approval_store)
    escalation_service = LLMAgentRiskEscalationService(gate, store=escalation_store)
    escalation = _pending_escalation(gate, escalation_service)

    expiration = LLMAgentRiskExpirationService(approval_store, escalation_store)

    assert expiration.is_expired(escalation, escalation.expires_at - timedelta(seconds=1)) is False
    assert expiration.is_expired(escalation, escalation.expires_at) is True
    assert expiration.is_expired(escalation, escalation.expires_at + timedelta(days=1)) is True


# --- already approved/rejected ------------------------------------------------


def test_already_approved_is_never_expired_even_long_after_its_original_window():
    store = InMemoryApprovalRequirementStore()
    gate = LLMAgentRiskApprovalGate(store=store, approval_window=timedelta(seconds=1))
    requirement = _required_requirement(gate)
    approved = gate.approve(requirement.request_id, "reviewer:ada")

    expiration = LLMAgentRiskExpirationService(store)
    long_after = approved.expires_at + timedelta(days=365)

    assert expiration.is_expired(approved, long_after) is False


def test_expire_pending_never_rewrites_an_already_resolved_record():
    store = InMemoryApprovalRequirementStore()
    gate = LLMAgentRiskApprovalGate(store=store, approval_window=timedelta(seconds=1))
    requirement = _required_requirement(gate)
    approved = gate.approve(requirement.request_id, "reviewer:ada")

    expiration = LLMAgentRiskExpirationService(store)
    far_future = approved.expires_at + timedelta(days=365)

    transitioned = expiration.expire_pending("notebook-1", far_future)

    assert transitioned == []
    assert store.get(requirement.request_id).status == APPROVAL_APPROVED


def test_invalid_expiration_target_raises():
    expiration = LLMAgentRiskExpirationService(InMemoryApprovalRequirementStore())
    with pytest.raises(InvalidExpirationTargetError):
        expiration.is_expired("not-a-requirement-or-escalation", datetime.now(timezone.utc))


# --- expired approval blocks execution ------------------------------------------


def test_expire_pending_durably_marks_a_stale_approval_and_blocks_further_decisions():
    store = InMemoryApprovalRequirementStore()
    gate = LLMAgentRiskApprovalGate(store=store, approval_window=timedelta(seconds=1))
    requirement = _required_requirement(gate)

    expiration = LLMAgentRiskExpirationService(store)
    far_future = requirement.expires_at + timedelta(days=1)

    transitioned = expiration.expire_pending("notebook-1", far_future)

    assert len(transitioned) == 1
    assert transitioned[0].status == APPROVAL_EXPIRED
    assert store.get(requirement.request_id).status == APPROVAL_EXPIRED

    with pytest.raises(ExpiredApprovalError):
        gate.approve(requirement.request_id, "reviewer:ada")


# --- expired escalation blocks execution -----------------------------------------


def test_expire_pending_durably_marks_a_stale_escalation_and_blocks_resolution():
    approval_store = InMemoryApprovalRequirementStore()
    escalation_store = InMemoryEscalationStore()
    gate = LLMAgentRiskApprovalGate(store=approval_store)
    escalation_service = LLMAgentRiskEscalationService(
        gate, store=escalation_store, escalation_window=timedelta(seconds=1)
    )
    escalation = _pending_escalation(gate, escalation_service)

    expiration = LLMAgentRiskExpirationService(approval_store, escalation_store)
    far_future = escalation.expires_at + timedelta(days=1)

    transitioned = expiration.expire_pending("notebook-1", far_future)

    assert any(getattr(item, "escalation_id", None) == escalation.escalation_id for item in transitioned)
    assert escalation_store.get(escalation.escalation_id).status == ESCALATION_EXPIRED

    with pytest.raises(ExpiredEscalationError):
        escalation_service.resolve(escalation.escalation_id, ESCALATION_APPROVED, "senior:ada")

    # the underlying (also-stale) ApprovalRequirement was independently
    # expired by the very same sweep, in the same scope
    requirement_id = escalation.request_id
    assert approval_store.get(requirement_id).status == APPROVAL_EXPIRED


# --- scope isolation -----------------------------------------------------------


def test_expire_pending_is_scope_isolated():
    store = InMemoryApprovalRequirementStore()
    gate = LLMAgentRiskApprovalGate(store=store, approval_window=timedelta(seconds=1))
    requirement_a = _required_requirement(gate, scope_id="notebook-a")
    requirement_b = _required_requirement(gate, scope_id="notebook-b")

    expiration = LLMAgentRiskExpirationService(store)
    far_future = max(requirement_a.expires_at, requirement_b.expires_at) + timedelta(days=1)

    transitioned = expiration.expire_pending("notebook-a", far_future)

    assert [item.request_id for item in transitioned] == [requirement_a.request_id]
    assert store.get(requirement_a.request_id).status == APPROVAL_EXPIRED
    assert store.get(requirement_b.request_id).status == APPROVAL_REQUIRED  # untouched


def test_expire_pending_requires_a_scope_id():
    expiration = LLMAgentRiskExpirationService(InMemoryApprovalRequirementStore())
    with pytest.raises(ValueError):
        expiration.expire_pending("", datetime.now(timezone.utc))
