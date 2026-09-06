from datetime import timedelta

import pytest

from backend.agent_policy_risk_approval import APPROVED, LLMAgentRiskApprovalGate
from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW, LEVEL_MEDIUM
from backend.agent_policy_risk_classification import RiskClassification
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine
from backend.agent_policy_risk_review_metrics import (
    InvalidMetricsFilterError,
    LLMAgentRiskReviewMetrics,
    ReviewMetrics,
    SecretInScopeError,
)
from backend.agent_policy_risk_review_queue import CLAIMED, EXPIRED, PENDING, RESOLVED, LLMAgentRiskReviewQueue
from backend.agent_policy_risk_thresholds import RiskThresholds

ACTION_CONTEXT = {"scope_id": "notebook-1", "plan_id": "plan-1", "tool_name": "delete", "arguments": {}}

# review_at=MEDIUM (instead of the default HIGH) so both MEDIUM and HIGH
# classifications resolve to REVIEW -- CRITICAL always resolves to DENY
# under any valid thresholds (Commit #3's own structural guarantee), so
# it can never be synthesized as a REVIEW decision here or anywhere else.
_WIDE_REVIEW_THRESHOLDS = RiskThresholds(scope_id="notebook-1", review_at=LEVEL_MEDIUM)


def _classification(risk_level, risk_factors=None):
    return RiskClassification(
        risk_level=risk_level, confidence="HIGH", evidence={}, risk_factors=risk_factors or {},
        reasons=["synthetic"], provenance={},
    )


def _review_decision(scope_id, step_id, risk_level=LEVEL_HIGH, risk_factors=None, thresholds=None):
    context = {**ACTION_CONTEXT, "scope_id": scope_id, "step_id": step_id}
    decision = LLMAgentPolicyRiskDecisionEngine().decide(
        context, _classification(risk_level, risk_factors), thresholds
    )
    return decision, context


def _setup(approval_window=None):
    gate = LLMAgentRiskApprovalGate(**({"approval_window": approval_window} if approval_window else {}))
    queue = LLMAgentRiskReviewQueue(gate)
    metrics = LLMAgentRiskReviewMetrics(queue)
    return gate, queue, metrics


def _enqueue(queue, step_id, scope_id="notebook-1", risk_level=LEVEL_HIGH, risk_factors=None, thresholds=None):
    decision, context = _review_decision(
        scope_id, step_id, risk_level, risk_factors or {"prior_denied_actions": 4}, thresholds
    )
    return queue.enqueue(decision, context)


# --- aggregate counts ------------------------------------------------------------


def test_aggregate_counts():
    gate, queue, metrics = _setup()
    pending_item = _enqueue(queue, "step-1")
    claimed_item = _enqueue(queue, "step-2")
    queue.claim(claimed_item.item_id, "reviewer:ada")
    resolved_item = _enqueue(queue, "step-3")
    queue.claim(resolved_item.item_id, "reviewer:bob")
    queue.complete(resolved_item.item_id, {"outcome": APPROVED})

    summary = metrics.summarize("notebook-1")

    assert isinstance(summary, ReviewMetrics)
    assert summary.total == 3
    assert summary.by_status[PENDING] == 1
    assert summary.by_status[CLAIMED] == 1
    assert summary.by_status[RESOLVED] == 1
    assert summary.by_status[EXPIRED] == 0


def test_expired_items_are_counted_via_effective_status():
    gate, queue, metrics = _setup(approval_window=timedelta(seconds=-1))
    _enqueue(queue, "step-1")

    summary = metrics.summarize("notebook-1")
    assert summary.by_status[EXPIRED] == 1
    assert summary.by_status[PENDING] == 0


# --- risk-level breakdown ----------------------------------------------------------


def test_risk_level_breakdown():
    gate, queue, metrics = _setup()
    _enqueue(queue, "step-1", risk_level=LEVEL_HIGH)
    _enqueue(queue, "step-2", risk_level=LEVEL_HIGH)
    # MEDIUM only resolves to REVIEW (rather than ALLOW) under a
    # widened review_at threshold -- CRITICAL can never appear here at
    # all, since it always resolves to DENY regardless of thresholds.
    _enqueue(queue, "step-3", risk_level=LEVEL_MEDIUM, risk_factors={}, thresholds=_WIDE_REVIEW_THRESHOLDS)

    summary = metrics.summarize("notebook-1")

    assert summary.by_risk_level[LEVEL_HIGH] == 2
    assert summary.by_risk_level[LEVEL_MEDIUM] == 1
    assert summary.by_risk_level[LEVEL_CRITICAL] == 0
    assert summary.by_risk_level[LEVEL_LOW] == 0


# --- approval/rejection counts -----------------------------------------------------


def test_approval_rejection_counts():
    gate, queue, metrics = _setup()
    approved = _enqueue(queue, "step-1")
    queue.claim(approved.item_id, "reviewer:ada")
    queue.complete(approved.item_id, {"outcome": "APPROVED"})

    rejected = _enqueue(queue, "step-2")
    queue.claim(rejected.item_id, "reviewer:bob")
    queue.complete(rejected.item_id, {"outcome": "REJECTED", "reason": "too risky"})

    unresolved = _enqueue(queue, "step-3")

    summary = metrics.summarize("notebook-1")

    assert summary.by_outcome["APPROVED"] == 1
    assert summary.by_outcome["REJECTED"] == 1
    assert summary.by_status[RESOLVED] == 2
    assert summary.by_status[PENDING] == 1


# --- resolution latency --------------------------------------------------------------


def test_average_resolution_latency():
    from dataclasses import replace as dc_replace

    gate, queue, metrics = _setup()
    item_1 = _enqueue(queue, "step-1")
    queue.claim(item_1.item_id, "reviewer:ada")
    resolved_1 = queue.complete(item_1.item_id, {"outcome": "APPROVED"})
    # force a known, deterministic latency rather than relying on real wall-clock timing
    aged_1 = dc_replace(resolved_1, resolved_at=resolved_1.created_at + timedelta(seconds=10))
    queue.store.save(aged_1)

    item_2 = _enqueue(queue, "step-2")
    queue.claim(item_2.item_id, "reviewer:bob")
    resolved_2 = queue.complete(item_2.item_id, {"outcome": "APPROVED"})
    aged_2 = dc_replace(resolved_2, resolved_at=resolved_2.created_at + timedelta(seconds=30))
    queue.store.save(aged_2)

    summary = metrics.summarize("notebook-1")
    assert summary.average_resolution_seconds == pytest.approx(20.0)


def test_average_resolution_is_zero_with_no_resolved_items():
    gate, queue, metrics = _setup()
    _enqueue(queue, "step-1")

    summary = metrics.summarize("notebook-1")
    assert summary.average_resolution_seconds == 0.0


# --- reviewer workload -----------------------------------------------------------------


def test_reviewer_workload():
    gate, queue, metrics = _setup()
    claimed = _enqueue(queue, "step-1")
    queue.claim(claimed.item_id, "reviewer:ada")

    resolved = _enqueue(queue, "step-2")
    queue.claim(resolved.item_id, "reviewer:ada")
    queue.complete(resolved.item_id, {"outcome": "APPROVED"})

    other = _enqueue(queue, "step-3")
    queue.claim(other.item_id, "reviewer:bob")
    queue.complete(other.item_id, {"outcome": "REJECTED", "reason": "no"})

    summary = metrics.summarize("notebook-1")

    assert summary.reviewer_workload["reviewer:ada"] == {"active": 1, "resolved": 1}
    assert summary.reviewer_workload["reviewer:bob"] == {"active": 0, "resolved": 1}
    assert "reviewer:carol" not in summary.reviewer_workload  # never claimed anything


# --- filters -----------------------------------------------------------------------------


def test_filters_by_status_and_risk_level():
    gate, queue, metrics = _setup()
    _enqueue(queue, "step-1", risk_level=LEVEL_HIGH)
    claimed = _enqueue(
        queue, "step-2", risk_level=LEVEL_MEDIUM, risk_factors={}, thresholds=_WIDE_REVIEW_THRESHOLDS
    )
    queue.claim(claimed.item_id, "reviewer:ada")

    only_pending = metrics.summarize("notebook-1", {"status": PENDING})
    assert only_pending.total == 1
    assert only_pending.by_status[PENDING] == 1

    only_medium = metrics.summarize("notebook-1", {"risk_level": LEVEL_MEDIUM})
    assert only_medium.total == 1
    assert only_medium.by_risk_level[LEVEL_MEDIUM] == 1


def test_filters_by_reviewer_and_time_bounds():
    gate, queue, metrics = _setup()
    item = _enqueue(queue, "step-1")
    queue.claim(item.item_id, "reviewer:ada")

    assert metrics.summarize("notebook-1", {"reviewer": "reviewer:ada"}).total == 1
    assert metrics.summarize("notebook-1", {"reviewer": "reviewer:nobody"}).total == 0

    far_future = item.created_at + timedelta(days=1)
    assert metrics.summarize("notebook-1", {"start": far_future}).total == 0
    assert metrics.summarize("notebook-1", {"end": far_future}).total == 1


def test_invalid_filters_rejected():
    gate, queue, metrics = _setup()
    with pytest.raises(InvalidMetricsFilterError):
        metrics.summarize("notebook-1", {"status": "NOT-A-STATUS"})
    with pytest.raises(InvalidMetricsFilterError):
        metrics.summarize("notebook-1", {"risk_level": "NOT-A-LEVEL"})
    with pytest.raises(InvalidMetricsFilterError):
        metrics.summarize("notebook-1", "not-a-dict")


# --- empty scope -----------------------------------------------------------------------------


def test_empty_scope_is_handled_cleanly():
    gate, queue, metrics = _setup()

    summary = metrics.summarize("never-used-scope")

    assert summary.total == 0
    assert all(count == 0 for count in summary.by_status.values())
    assert all(count == 0 for count in summary.by_outcome.values())
    assert all(count == 0 for count in summary.by_risk_level.values())
    assert summary.average_resolution_seconds == 0.0
    assert summary.reviewer_workload == {}


def test_secret_looking_scope_is_rejected():
    gate, queue, metrics = _setup()
    with pytest.raises(SecretInScopeError):
        metrics.summarize("api_key: sk-abcdefghijklmnopqrstuvwxyz")


# --- scope isolation -----------------------------------------------------------------------------


def test_scope_isolation():
    gate, queue, metrics = _setup()
    _enqueue(queue, "step-1", scope_id="notebook-a")
    _enqueue(queue, "step-2", scope_id="notebook-b")
    _enqueue(queue, "step-3", scope_id="notebook-b")

    assert metrics.summarize("notebook-a").total == 1
    assert metrics.summarize("notebook-b").total == 2


def test_summary_never_exposes_action_payload():
    gate, queue, metrics = _setup()
    decision, context = _review_decision("notebook-1", "step-1")
    context = {**context, "arguments": {"password": "hunter2"}}
    queue.enqueue(decision, context)

    summary = metrics.summarize("notebook-1")
    dumped = str(summary)
    assert "hunter2" not in dumped
    assert "arguments" not in dumped
