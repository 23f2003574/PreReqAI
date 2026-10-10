from datetime import timedelta

import pytest

from backend.agent_policy_risk_approval import APPROVED as APPROVAL_APPROVED
from backend.agent_policy_risk_approval import LLMAgentRiskApprovalGate
from backend.agent_policy_risk_assessment import LEVEL_HIGH
from backend.agent_policy_risk_classification import RiskClassification
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine
from backend.agent_policy_risk_review_assignment import (
    ACTIVE,
    REVOKED,
    Assignment,
    AssignmentNotAllowedError,
    LLMAgentRiskReviewAssignment,
    NotAssignedError,
    UnauthorizedReviewerError,
)
from backend.agent_policy_risk_review_queue import CLAIMED, LLMAgentRiskReviewQueue

ACTION_CONTEXT = {"scope_id": "notebook-1", "plan_id": "plan-1", "step_id": "step-1", "tool_name": "delete", "arguments": {}}


def _review_decision(scope_id="notebook-1"):
    classification = RiskClassification(
        risk_level=LEVEL_HIGH, confidence="HIGH", evidence={}, risk_factors={"prior_denied_actions": 4},
        reasons=["synthetic high risk"], provenance={},
    )
    context = {**ACTION_CONTEXT, "scope_id": scope_id}
    return LLMAgentPolicyRiskDecisionEngine().decide(context, classification), context


def _allow_all(reviewer, scope_id):
    return True


def _setup(authorization=_allow_all, approval_window=None):
    gate = LLMAgentRiskApprovalGate(**({"approval_window": approval_window} if approval_window else {}))
    queue = LLMAgentRiskReviewQueue(gate)
    assignment = LLMAgentRiskReviewAssignment(queue, authorization)
    return gate, queue, assignment


def _enqueued_item(queue, scope_id="notebook-1"):
    decision, context = _review_decision(scope_id)
    return queue.enqueue(decision, context)


# --- valid assignment -----------------------------------------------------------


def test_valid_assignment():
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)

    assignment = assignment_service.assign(item.item_id, "reviewer:ada", assigned_by="lead:sam")

    assert isinstance(assignment, Assignment)
    assert assignment.status == ACTIVE
    assert assignment.reviewer == "reviewer:ada"
    assert assignment.assigned_by == "lead:sam"
    assert assignment.assigned_at is not None

    # integration: assigning also claims the item in Commit #8's queue
    assert queue.get(item.item_id).status == CLAIMED
    assert queue.get(item.item_id).claimed_by == "reviewer:ada"


def test_self_assignment_defaults_assigned_by_to_the_reviewer():
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)

    assignment = assignment_service.assign(item.item_id, "reviewer:ada")
    assert assignment.assigned_by == "reviewer:ada"


# --- unauthorized reviewer ----------------------------------------------------


def test_unauthorized_reviewer_is_rejected():
    def only_ada(reviewer, scope_id):
        return reviewer == "reviewer:ada"

    gate, queue, assignment_service = _setup(authorization=only_ada)
    item = _enqueued_item(queue)

    with pytest.raises(UnauthorizedReviewerError):
        assignment_service.assign(item.item_id, "reviewer:mallory")

    # the unauthorized attempt never touched the queue either
    assert queue.get(item.item_id).status != CLAIMED
    assert assignment_service.get_assignment(item.item_id) is None


# --- duplicate/conflicting assignment -------------------------------------------


def test_duplicate_assignment_to_the_same_reviewer_is_idempotent():
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)

    first = assignment_service.assign(item.item_id, "reviewer:ada")
    second = assignment_service.assign(item.item_id, "reviewer:ada")

    assert first == second
    assert len(assignment_service.history(item.item_id)) == 1


def test_conflicting_assignment_to_a_second_reviewer_reassigns():
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)
    assignment_service.assign(item.item_id, "reviewer:ada")

    second = assignment_service.assign(item.item_id, "reviewer:bob")

    assert second.reviewer == "reviewer:bob"
    assert second.status == ACTIVE
    assert assignment_service.get_assignment(item.item_id).reviewer == "reviewer:bob"


# --- reassignment ------------------------------------------------------------------


def test_reassignment_preserves_history():
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)
    first = assignment_service.assign(item.item_id, "reviewer:ada")

    second = assignment_service.assign(item.item_id, "reviewer:bob")

    history = assignment_service.history(item.item_id)
    assert [entry.assignment_id for entry in history] == [first.assignment_id, second.assignment_id]
    assert assignment_service.store.get(first.assignment_id).status == REVOKED
    assert assignment_service.store.get(first.assignment_id).revoked_at is not None
    assert assignment_service.store.get(second.assignment_id).status == ACTIVE


def test_reassignment_does_not_force_a_queue_takeover():
    # ada claims the item directly through Commit #8 (not via assignment);
    # reassigning to bob must not raise, and must not silently steal
    # ada's real queue-level ownership out from under her.
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)
    queue.claim(item.item_id, "reviewer:ada")

    bob_assignment = assignment_service.assign(item.item_id, "reviewer:bob")

    assert bob_assignment.reviewer == "reviewer:bob"
    assert queue.get(item.item_id).claimed_by == "reviewer:ada"  # untouched


# --- unassignment ------------------------------------------------------------------


def test_unassignment():
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)
    assignment_service.assign(item.item_id, "reviewer:ada")

    revoked = assignment_service.unassign(item.item_id, "reviewer:ada")

    assert revoked.status == REVOKED
    assert assignment_service.get_assignment(item.item_id) is None


def test_unassigning_a_reviewer_who_does_not_hold_it_raises():
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)
    assignment_service.assign(item.item_id, "reviewer:ada")

    with pytest.raises(NotAssignedError):
        assignment_service.unassign(item.item_id, "reviewer:bob")


def test_unassigned_items_remain_claimable():
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)
    assignment_service.assign(item.item_id, "reviewer:ada")
    assignment_service.unassign(item.item_id, "reviewer:ada")

    # Commit #8's own claim() is untouched by assignment state -- ada's
    # earlier auto-claim still stands, but a never-assigned item is
    # claimable by anyone as always. Demonstrate on a second, fresh item.
    other_decision, other_context = _review_decision()
    other_context = {**other_context, "step_id": "step-2"}
    other_item = queue.enqueue(other_decision, other_context)

    claimed = queue.claim(other_item.item_id, "reviewer:carol")
    assert claimed.status == CLAIMED
    assert assignment_service.get_assignment(other_item.item_id) is None


# --- expired/resolved item ----------------------------------------------------------


def test_cannot_assign_a_resolved_item():
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)
    queue.claim(item.item_id, "reviewer:ada")
    queue.complete(item.item_id, {"outcome": APPROVAL_APPROVED})

    with pytest.raises(AssignmentNotAllowedError):
        assignment_service.assign(item.item_id, "reviewer:bob")


def test_cannot_assign_an_expired_item():
    gate, queue, assignment_service = _setup(approval_window=timedelta(seconds=-1))
    item = _enqueued_item(queue)

    with pytest.raises(AssignmentNotAllowedError):
        assignment_service.assign(item.item_id, "reviewer:ada")


# --- reviewer filtering --------------------------------------------------------------


def test_reviewer_filtering():
    gate, queue, assignment_service = _setup()
    item_1 = _enqueued_item(queue)
    decision_2, context_2 = _review_decision()
    context_2 = {**context_2, "step_id": "step-2"}
    item_2 = queue.enqueue(decision_2, context_2)

    assignment_service.assign(item_1.item_id, "reviewer:ada")
    assignment_service.assign(item_2.item_id, "reviewer:bob")

    ada_assignments = assignment_service.list_for_reviewer("reviewer:ada", "notebook-1")
    bob_assignments = assignment_service.list_for_reviewer("reviewer:bob", "notebook-1")

    assert [a.item_id for a in ada_assignments] == [item_1.item_id]
    assert [a.item_id for a in bob_assignments] == [item_2.item_id]


# --- scope isolation --------------------------------------------------------------


def test_scope_isolation():
    gate, queue, assignment_service = _setup()
    item_a = _enqueued_item(queue, scope_id="notebook-a")
    item_b = _enqueued_item(queue, scope_id="notebook-b")

    assignment_service.assign(item_a.item_id, "reviewer:ada")

    assert assignment_service.list_for_reviewer("reviewer:ada", "notebook-a")
    assert assignment_service.list_for_reviewer("reviewer:ada", "notebook-b") == []
    assert assignment_service.get_assignment(item_b.item_id) is None


def test_authorization_is_checked_per_scope():
    def only_notebook_a(reviewer, scope_id):
        return scope_id == "notebook-a"

    gate, queue, assignment_service = _setup(authorization=only_notebook_a)
    item_a = _enqueued_item(queue, scope_id="notebook-a")
    item_b = _enqueued_item(queue, scope_id="notebook-b")

    assignment_service.assign(item_a.item_id, "reviewer:ada")  # fine
    with pytest.raises(UnauthorizedReviewerError):
        assignment_service.assign(item_b.item_id, "reviewer:ada")


# --- provenance ----------------------------------------------------------------------


def test_provenance_preserves_the_review_item_and_actors():
    gate, queue, assignment_service = _setup()
    item = _enqueued_item(queue)

    assignment = assignment_service.assign(item.item_id, "reviewer:ada", assigned_by="lead:sam")

    assert assignment.provenance["item_id"] == item.item_id
    assert assignment.provenance["scope_id"] == "notebook-1"
    assert assignment.provenance["reviewer"] == "reviewer:ada"
    assert assignment.provenance["assigned_by"] == "lead:sam"
    assert assignment.provenance["review_item"].item_id == item.item_id
    assert assignment.provenance["review_item"].decision.risk_level == LEVEL_HIGH
