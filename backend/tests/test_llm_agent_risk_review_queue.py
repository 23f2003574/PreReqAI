from datetime import timedelta

import pytest

from backend.agent_policy_risk_approval import (
    APPROVED as APPROVAL_APPROVED,
)
from backend.agent_policy_risk_approval import (
    REJECTED as APPROVAL_REJECTED,
)
from backend.agent_policy_risk_approval import (
    InMemoryApprovalRequirementStore,
    LLMAgentRiskApprovalGate,
)
from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW
from backend.agent_policy_risk_classification import RiskClassification
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine
from backend.agent_policy_risk_escalation import LLMAgentRiskEscalationService
from backend.agent_policy_risk_review_queue import (
    CLAIMED,
    EXPIRED,
    PENDING,
    RESOLVED,
    ConflictingClaimError,
    ExpiredReviewItemError,
    InvalidReviewItemTransitionError,
    LLMAgentRiskReviewQueue,
    NotReviewableError,
    ReviewItem,
    UnknownReviewItemError,
)

ACTION_CONTEXT = {"scope_id": "notebook-1", "plan_id": "plan-1", "step_id": "step-1", "tool_name": "delete", "arguments": {}}


def _classification(risk_level, risk_factors=None):
    return RiskClassification(
        risk_level=risk_level, confidence="HIGH", evidence={}, risk_factors=risk_factors or {},
        reasons=["synthetic"], provenance={},
    )


def _review_decision(scope_id="notebook-1"):
    context = {**ACTION_CONTEXT, "scope_id": scope_id}
    classification = _classification(LEVEL_HIGH, {"prior_denied_actions": 4})
    return LLMAgentPolicyRiskDecisionEngine().decide(context, classification), context


def _allow_decision(scope_id="notebook-1"):
    context = {**ACTION_CONTEXT, "scope_id": scope_id}
    classification = _classification(LEVEL_LOW)
    return LLMAgentPolicyRiskDecisionEngine().decide(context, classification), context


def _queue():
    gate = LLMAgentRiskApprovalGate()
    queue = LLMAgentRiskReviewQueue(gate)
    return gate, queue


# --- enqueue review -----------------------------------------------------------


def test_enqueue_review():
    gate, queue = _queue()
    decision, context = _review_decision()

    item = queue.enqueue(decision, context)

    assert isinstance(item, ReviewItem)
    assert item.status == PENDING
    assert item.scope_id == "notebook-1"
    assert item.approval_request_id
    assert item.expires_at is not None


# --- non-review exclusion -----------------------------------------------------


def test_allow_decision_cannot_be_enqueued():
    gate, queue = _queue()
    decision, context = _allow_decision()

    with pytest.raises(NotReviewableError):
        queue.enqueue(decision, context)


def test_deny_decision_cannot_be_enqueued():
    from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
    from backend.agent_policy_engine import DENY, LLMAgentPolicyRule, LLMAgentPolicyService
    from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement
    from backend.agent_policy_resolution import LLMAgentPolicyResolver
    from backend.agent_policy_risk_assessment import LLMAgentPolicyRiskAssessor
    from backend.agent_policy_risk_classification import LLMAgentPolicyRiskClassifier

    policy_service = LLMAgentPolicyService()
    policy_service.create("notebook-1", "deny-policy", [
        LLMAgentPolicyRule(rule_id="deny-delete", effect=DENY, match={"tool_name": "delete"})
    ])
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    assessment = LLMAgentPolicyRiskAssessor(enforcement).assess(ACTION_CONTEXT)
    classification = LLMAgentPolicyRiskClassifier().classify(assessment)
    decision = LLMAgentPolicyRiskDecisionEngine().decide(ACTION_CONTEXT, classification)
    assert decision.decision == "DENY"  # sanity

    gate, queue = _queue()
    with pytest.raises(NotReviewableError):
        queue.enqueue(decision, ACTION_CONTEXT)


# --- claim ownership -----------------------------------------------------------


def test_claim_ownership():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)

    claimed = queue.claim(item.item_id, "reviewer:ada")

    assert claimed.status == CLAIMED
    assert claimed.claimed_by == "reviewer:ada"
    assert claimed.claimed_at is not None


def test_reclaiming_by_the_same_actor_is_idempotent():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    first = queue.claim(item.item_id, "reviewer:ada")

    second = queue.claim(item.item_id, "reviewer:ada")
    assert second == first


# --- conflicting claim -----------------------------------------------------------


def test_conflicting_claim_is_rejected():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    queue.claim(item.item_id, "reviewer:ada")

    with pytest.raises(ConflictingClaimError):
        queue.claim(item.item_id, "reviewer:bob")


def test_cannot_claim_a_resolved_item():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    queue.claim(item.item_id, "reviewer:ada")
    queue.complete(item.item_id, {"outcome": APPROVAL_APPROVED})

    with pytest.raises(InvalidReviewItemTransitionError):
        queue.claim(item.item_id, "reviewer:bob")


# --- resolution -----------------------------------------------------------------


def test_resolution_approves_through_the_gate():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    queue.claim(item.item_id, "reviewer:ada")

    resolved = queue.complete(item.item_id, {"outcome": APPROVAL_APPROVED})

    assert resolved.status == RESOLVED
    assert resolved.resolution == {"outcome": APPROVAL_APPROVED, "reason": None}
    assert gate.get(item.approval_request_id).status == APPROVAL_APPROVED
    assert gate.get(item.approval_request_id).actor == "reviewer:ada"


def test_resolution_rejects_through_the_gate():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    queue.claim(item.item_id, "reviewer:ada")

    resolved = queue.complete(item.item_id, {"outcome": APPROVAL_REJECTED, "reason": "too risky"})

    assert resolved.status == RESOLVED
    assert gate.get(item.approval_request_id).status == APPROVAL_REJECTED
    assert gate.get(item.approval_request_id).reason == "too risky"


def test_rejection_requires_a_reason():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    queue.claim(item.item_id, "reviewer:ada")

    with pytest.raises(ValueError):
        queue.complete(item.item_id, {"outcome": APPROVAL_REJECTED})


def test_completing_an_unclaimed_item_is_rejected():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)

    with pytest.raises(InvalidReviewItemTransitionError):
        queue.complete(item.item_id, {"outcome": APPROVAL_APPROVED})


def test_resolution_flows_through_escalation_when_active():
    approval_store = InMemoryApprovalRequirementStore()
    gate = LLMAgentRiskApprovalGate(store=approval_store)
    escalation_service = LLMAgentRiskEscalationService(gate)
    queue = LLMAgentRiskReviewQueue(gate, escalation_service=escalation_service)

    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    queue.claim(item.item_id, "reviewer:ada")
    escalation = escalation_service.escalate(item.approval_request_id, "needs senior review")

    resolved = queue.complete(item.item_id, {"outcome": APPROVAL_APPROVED})

    assert resolved.escalation_id == escalation.escalation_id
    assert escalation_service.get(escalation.escalation_id).status == APPROVAL_APPROVED
    assert gate.get(item.approval_request_id).status == APPROVAL_APPROVED
    assert gate.get(item.approval_request_id).actor == "reviewer:ada"


# --- expiration -----------------------------------------------------------------


def test_expired_item_cannot_be_claimed():
    gate = LLMAgentRiskApprovalGate(approval_window=timedelta(seconds=-1))
    queue = LLMAgentRiskReviewQueue(gate)
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)

    assert queue.get(item.item_id).status == EXPIRED
    with pytest.raises(ExpiredReviewItemError):
        queue.claim(item.item_id, "reviewer:ada")


def test_expired_item_cannot_be_completed_even_if_previously_claimed():
    gate = LLMAgentRiskApprovalGate(approval_window=timedelta(minutes=5))
    queue = LLMAgentRiskReviewQueue(gate)
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    claimed = queue.claim(item.item_id, "reviewer:ada")

    # forcibly age the item past its own deadline, simulating a claim
    # that was never completed in time
    from dataclasses import replace as dc_replace
    stale = dc_replace(claimed, expires_at=claimed.claimed_at - timedelta(seconds=1))
    queue.store.save(stale)

    with pytest.raises(ExpiredReviewItemError):
        queue.complete(item.item_id, {"outcome": APPROVAL_APPROVED})


def test_unknown_item_id_raises():
    gate, queue = _queue()
    with pytest.raises(UnknownReviewItemError):
        queue.get("does-not-exist")
    with pytest.raises(UnknownReviewItemError):
        queue.claim("does-not-exist", "reviewer:ada")


# --- scope isolation -----------------------------------------------------------


def test_scope_isolation():
    gate, queue = _queue()
    decision_a, context_a = _review_decision("notebook-a")
    decision_b, context_b = _review_decision("notebook-b")

    item_a = queue.enqueue(decision_a, context_a)
    item_b = queue.enqueue(decision_b, context_b)

    scope_a_items = queue.list("notebook-a")
    scope_b_items = queue.list("notebook-b")

    assert [item.item_id for item in scope_a_items] == [item_a.item_id]
    assert [item.item_id for item in scope_b_items] == [item_b.item_id]

    queue.claim(item_a.item_id, "reviewer:ada")
    assert queue.get(item_b.item_id).status == PENDING  # untouched by scope A's claim


def test_list_filters_by_status():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    queue.claim(item.item_id, "reviewer:ada")

    assert [i.item_id for i in queue.list("notebook-1", status=CLAIMED)] == [item.item_id]
    assert queue.list("notebook-1", status=PENDING) == []


# --- provenance -----------------------------------------------------------------


def test_provenance_preserves_decision_evidence_and_references():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)

    assert item.provenance["approval_request_id"] == item.approval_request_id
    assert item.provenance["decision"] == item.decision
    assert item.provenance["action_context"] == item.action_context
    assert item.decision.risk_level == LEVEL_HIGH
    assert item.decision.risk_factors == {"prior_denied_actions": 4}


# --- duplicate enqueue -----------------------------------------------------------


def test_duplicate_enqueue_returns_the_same_item():
    gate, queue = _queue()
    decision, context = _review_decision()

    first = queue.enqueue(decision, context)
    second = queue.enqueue(decision, context)

    assert first.item_id == second.item_id


def test_duplicate_enqueue_after_resolution_returns_the_resolved_item():
    gate, queue = _queue()
    decision, context = _review_decision()
    item = queue.enqueue(decision, context)
    queue.claim(item.item_id, "reviewer:ada")
    queue.complete(item.item_id, {"outcome": APPROVAL_APPROVED})

    again = queue.enqueue(decision, context)
    assert again.item_id == item.item_id
    assert again.status == RESOLVED
