import json
from datetime import timedelta

import pytest

from backend.agent_policy_risk_approval import LLMAgentRiskApprovalGate
from backend.agent_policy_risk_assessment import LEVEL_HIGH, LEVEL_MEDIUM
from backend.agent_policy_risk_classification import RiskClassification
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine
from backend.agent_policy_risk_review_metrics import LLMAgentRiskReviewMetrics
from backend.agent_policy_risk_review_queue import CLAIMED, EXPIRED, PENDING, LLMAgentRiskReviewQueue
from backend.agent_policy_risk_review_reporting import (
    LLMAgentRiskReviewReportService,
    ReviewReport,
    UnsupportedFormatError,
)
from backend.agent_policy_risk_thresholds import RiskThresholds

ACTION_CONTEXT = {"scope_id": "notebook-1", "plan_id": "plan-1", "tool_name": "delete", "arguments": {}}
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


def _enqueue(queue, step_id, scope_id="notebook-1", risk_level=LEVEL_HIGH, risk_factors=None, thresholds=None):
    decision, context = _review_decision(
        scope_id, step_id, risk_level, risk_factors or {"prior_denied_actions": 4}, thresholds
    )
    return queue.enqueue(decision, context)


def _setup(approval_window=None):
    gate = LLMAgentRiskApprovalGate(**({"approval_window": approval_window} if approval_window else {}))
    queue = LLMAgentRiskReviewQueue(gate)
    metrics = LLMAgentRiskReviewMetrics(queue)
    report_service = LLMAgentRiskReviewReportService(metrics)
    return gate, queue, report_service


# --- report generation -----------------------------------------------------------


def test_report_generation():
    gate, queue, report_service = _setup()
    pending = _enqueue(queue, "step-1")
    claimed = _enqueue(queue, "step-2")
    queue.claim(claimed.item_id, "reviewer:ada")
    resolved = _enqueue(queue, "step-3")
    queue.claim(resolved.item_id, "reviewer:bob")
    queue.complete(resolved.item_id, {"outcome": "APPROVED"})

    report = report_service.generate("notebook-1")

    assert isinstance(report, ReviewReport)
    assert report.scope_id == "notebook-1"
    assert report.volume["total"] == 3
    assert report.volume["by_status"][PENDING] == 1
    assert report.volume["by_status"][CLAIMED] == 1
    assert report.generated_at is not None


def test_export_is_deterministic_json():
    gate, queue, report_service = _setup()
    _enqueue(queue, "step-1")
    report = report_service.generate("notebook-1")

    first = report_service.export(report)
    second = report_service.export(report)
    assert first == second
    assert json.loads(first)["scope_id"] == "notebook-1"


def test_export_rejects_unsupported_format():
    gate, queue, report_service = _setup()
    report = report_service.generate("notebook-1")
    with pytest.raises(UnsupportedFormatError):
        report_service.export(report, format="xml")


# --- filters -----------------------------------------------------------------------


def test_filters_are_echoed_and_applied():
    gate, queue, report_service = _setup()
    item = _enqueue(queue, "step-1")
    queue.claim(item.item_id, "reviewer:ada")

    report = report_service.generate("notebook-1", {"status": CLAIMED})

    assert report.filters == {"status": CLAIMED}
    assert report.volume["total"] == 1
    assert report.volume["by_status"][CLAIMED] == 1


# --- empty data -----------------------------------------------------------------------


def test_empty_data_produces_a_clean_report():
    gate, queue, report_service = _setup()

    report = report_service.generate("never-used-scope")

    assert report.volume["total"] == 0
    assert all(count == 0 for count in report.volume["by_status"].values())
    assert all(count == 0 for count in report.approval_vs_rejection.values())
    assert all(count == 0 for count in report.risk_level_distribution.values())
    assert report.reviewer_workload == []
    assert report.resolution_time == {"average_seconds": 0.0}
    assert report.pending_items == []
    assert report.expired_items == []


# --- risk/status breakdown --------------------------------------------------------------


def test_risk_and_status_breakdown():
    gate, queue, report_service = _setup()
    _enqueue(queue, "step-1", risk_level=LEVEL_HIGH)
    _enqueue(queue, "step-2", risk_level=LEVEL_MEDIUM, risk_factors={}, thresholds=_WIDE_REVIEW_THRESHOLDS)

    report = report_service.generate("notebook-1")

    assert report.risk_level_distribution[LEVEL_HIGH] == 1
    assert report.risk_level_distribution[LEVEL_MEDIUM] == 1
    assert report.volume["by_status"][PENDING] == 2


def test_approval_vs_rejection_breakdown():
    gate, queue, report_service = _setup()
    approved = _enqueue(queue, "step-1")
    queue.claim(approved.item_id, "reviewer:ada")
    queue.complete(approved.item_id, {"outcome": "APPROVED"})

    rejected = _enqueue(queue, "step-2")
    queue.claim(rejected.item_id, "reviewer:bob")
    queue.complete(rejected.item_id, {"outcome": "REJECTED", "reason": "too risky"})

    report = report_service.generate("notebook-1")
    assert report.approval_vs_rejection["APPROVED"] == 1
    assert report.approval_vs_rejection["REJECTED"] == 1


def test_expired_and_pending_items_are_listed():
    gate, queue, report_service = _setup(approval_window=timedelta(seconds=-1))
    stale = _enqueue(queue, "step-1")

    report = report_service.generate("notebook-1")

    assert report.expired_items == [
        {
            "item_id": stale.item_id,
            "scope_id": "notebook-1",
            "status": EXPIRED,
            "risk_level": LEVEL_HIGH,
            "created_at": stale.created_at,
            "expires_at": stale.expires_at,
        }
    ]
    assert report.pending_items == []


# --- reviewer statistics --------------------------------------------------------------------


def test_reviewer_statistics_are_ranked():
    gate, queue, report_service = _setup()
    busy = _enqueue(queue, "step-1")
    queue.claim(busy.item_id, "reviewer:ada")
    also_busy = _enqueue(queue, "step-2")
    queue.claim(also_busy.item_id, "reviewer:ada")

    quiet = _enqueue(queue, "step-3")
    queue.claim(quiet.item_id, "reviewer:bob")

    report = report_service.generate("notebook-1")

    assert report.reviewer_workload[0] == {"reviewer": "reviewer:ada", "active": 2, "resolved": 0}
    assert report.reviewer_workload[1] == {"reviewer": "reviewer:bob", "active": 1, "resolved": 0}


# --- provenance --------------------------------------------------------------------------------


def test_provenance_names_the_source_and_record_count():
    gate, queue, report_service = _setup()
    _enqueue(queue, "step-1")
    _enqueue(queue, "step-2")

    report = report_service.generate("notebook-1")

    assert report.provenance["source"] == "backend.agent_policy_risk_review_metrics.LLMAgentRiskReviewMetrics"
    assert report.provenance["record_count"] == 2


# --- sensitive-data exclusion ------------------------------------------------------------------


def test_report_never_exposes_action_payload():
    gate, queue, report_service = _setup()
    decision, context = _review_decision("notebook-1", "step-1")
    context = {**context, "arguments": {"password": "hunter2"}}
    queue.enqueue(decision, context)

    report = report_service.generate("notebook-1")
    dumped = report_service.export(report)

    assert "hunter2" not in dumped
    assert "arguments" not in dumped
    assert "password" not in dumped
