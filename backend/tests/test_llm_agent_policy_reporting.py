import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_audit import LLMAgentPolicyAuditService, LLMAgentPolicyDecisionAudit
from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_policy_metrics import LLMAgentPolicyMetricsService
from backend.agent_policy_reporting import (
    LLMAgentPolicyReportService,
    PolicyReport,
    UnsupportedFormatError,
)

NOW = datetime.now(timezone.utc)


def _record(audit_service, scope_id, decision, policy_id, rule_id, exceptions=None, created_at=None):
    audit = LLMAgentPolicyDecisionAudit(
        scope_id=scope_id,
        execution_or_action_id=f"exec-{policy_id}-{rule_id}-{created_at}",
        decision=decision,
        matched_rules=[{"policy_id": policy_id, "rule_id": rule_id, "effect": decision, "reason": "reason"}],
        exceptions=exceptions or [],
        reasons=["reason"],
        created_at=created_at or NOW,
    )
    return audit_service.store.save(audit)


def _services():
    audit_service = LLMAgentPolicyAuditService()
    metrics_service = LLMAgentPolicyMetricsService(audit_service)
    return audit_service, LLMAgentPolicyReportService(metrics_service)


def test_report_contents():
    audit_service, report_service = _services()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(
        audit_service, "notebook-1", ALLOW, "policy-b", "rule-2",
        exceptions=[{"exception_id": "exc-1", "policy_id": "policy-b", "reason": "approved"}],
    )
    _record(audit_service, "notebook-1", DENY, "policy-c", "rule-3")

    report = report_service.generate("notebook-1")

    assert isinstance(report, PolicyReport)
    assert report.scope_id == "notebook-1"
    assert report.decision_summary == {"total": 4, "allowed": 3, "denied": 1, "denial_rate": 0.25}
    assert report.exception_usage == {"exception_assisted": 1, "exception_rate": 0.25}
    assert report.top_policies[0] == {"id": "policy-a", "total": 2, "allowed": 2, "denied": 0}
    assert {"id": "policy-b", "total": 1, "allowed": 1, "denied": 0} in report.top_policies
    assert {"id": "policy-c", "total": 1, "allowed": 0, "denied": 1} in report.top_policies
    assert report.top_rules[0] == {"id": "rule-1", "total": 2, "allowed": 2, "denied": 0}
    assert len(report.trends) == 1  # all recorded "today"
    assert report.trends[0]["total"] == 4


def test_filters_are_forwarded_to_metrics():
    audit_service, report_service = _services()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1", created_at=NOW - timedelta(days=10))
    _record(audit_service, "notebook-1", DENY, "policy-b", "rule-2", created_at=NOW)

    full_report = report_service.generate("notebook-1")
    assert full_report.decision_summary["total"] == 2

    recent_only = report_service.generate(
        "notebook-1", filters={"start": NOW - timedelta(days=1), "end": NOW + timedelta(days=1)}
    )
    assert recent_only.decision_summary["total"] == 1
    assert recent_only.decision_summary["denied"] == 1

    only_allow = report_service.generate("notebook-1", filters={"decision": ALLOW})
    assert only_allow.decision_summary["total"] == 1
    assert only_allow.decision_summary["allowed"] == 1

    assert recent_only.filters == {"start": NOW - timedelta(days=1), "end": NOW + timedelta(days=1)}


def test_empty_data():
    _, report_service = _services()
    report = report_service.generate("empty-notebook")

    assert report.decision_summary == {"total": 0, "allowed": 0, "denied": 0, "denial_rate": 0.0}
    assert report.trends == []
    assert report.top_policies == []
    assert report.top_rules == []
    assert report.exception_usage == {"exception_assisted": 0, "exception_rate": 0.0}
    assert report.notable_changes == []
    assert report.provenance == {
        "source": "backend.agent_policy_audit.LLMAgentPolicyAuditService",
        "record_count": 0,
    }


def test_scope_isolation():
    audit_service, report_service = _services()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-2", DENY, "policy-a", "rule-1")

    report_1 = report_service.generate("notebook-1")
    report_2 = report_service.generate("notebook-2")

    assert report_1.decision_summary["total"] == 2
    assert report_1.decision_summary["denied"] == 0
    assert report_2.decision_summary["total"] == 1
    assert report_2.decision_summary["denied"] == 1


def test_provenance():
    audit_service, report_service = _services()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-1", DENY, "policy-b", "rule-2")

    report = report_service.generate("notebook-1")

    assert report.provenance["source"] == "backend.agent_policy_audit.LLMAgentPolicyAuditService"
    assert report.provenance["record_count"] == 2
    assert report.generated_at is not None


def test_notable_enforcement_changes_are_surfaced():
    audit_service, report_service = _services()
    day_one = NOW - timedelta(days=2)
    day_two = NOW

    for _ in range(9):
        _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1", created_at=day_one)
    _record(audit_service, "notebook-1", DENY, "policy-a", "rule-1", created_at=day_one)  # 10% denial that day

    for _ in range(2):
        _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1", created_at=day_two)
    for _ in range(8):
        _record(audit_service, "notebook-1", DENY, "policy-a", "rule-1", created_at=day_two)  # 80% denial that day

    report = report_service.generate("notebook-1")

    notable_periods = {entry["period"] for entry in report.notable_changes}
    assert day_two.date().isoformat() in notable_periods
    day_two_entry = next(entry for entry in report.notable_changes if entry["period"] == day_two.date().isoformat())
    assert day_two_entry["denial_rate"] == pytest.approx(0.8)


def test_sensitive_data_never_exposed():
    audit_service, report_service = _services()
    _record(audit_service, "notebook-1", DENY, "policy-a", "rule-1")

    report = report_service.generate("notebook-1")
    dumped = report_service.export(report)

    assert "arguments" not in dumped
    assert "topic" not in dumped


def test_deterministic_output():
    audit_service, report_service = _services()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-1", DENY, "policy-b", "rule-2")

    first = report_service.generate("notebook-1")
    second = report_service.generate("notebook-1")

    # generated_at is naturally wall-clock; everything else must match exactly
    first_without_timestamp = dataclasses.replace(first, generated_at=NOW)
    second_without_timestamp = dataclasses.replace(second, generated_at=NOW)
    assert first_without_timestamp == second_without_timestamp


def test_export_rejects_unsupported_format():
    _, report_service = _services()
    report = report_service.generate("notebook-1")

    with pytest.raises(UnsupportedFormatError):
        report_service.export(report, format="xml")

    assert isinstance(report_service.export(report), str)
