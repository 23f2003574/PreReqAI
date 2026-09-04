from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_audit import LLMAgentPolicyAuditService, LLMAgentPolicyDecisionAudit
from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_policy_metrics import (
    InvalidMetricsFilterError,
    LLMAgentPolicyMetricsService,
    PolicyMetrics,
    SecretInScopeError,
)

NOW = datetime.now(timezone.utc)


def _record(audit_service, scope_id, decision, policy_id, rule_id, exceptions=None, created_at=None):
    """Directly saves an LLMAgentPolicyDecisionAudit, bypassing record()
    so tests can control created_at precisely for time-range filtering --
    record() itself is already covered by Commit #7's own tests."""
    audit = LLMAgentPolicyDecisionAudit(
        scope_id=scope_id,
        execution_or_action_id=f"exec-{policy_id}-{rule_id}",
        decision=decision,
        matched_rules=[{"policy_id": policy_id, "rule_id": rule_id, "effect": decision, "reason": "reason"}],
        exceptions=exceptions or [],
        reasons=["reason"],
        created_at=created_at or NOW,
    )
    return audit_service.store.save(audit)


def test_aggregate_counts():
    audit_service = LLMAgentPolicyAuditService()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-2")
    _record(audit_service, "notebook-1", DENY, "policy-b", "rule-3")

    metrics = LLMAgentPolicyMetricsService(audit_service).summarize("notebook-1")

    assert isinstance(metrics, PolicyMetrics)
    assert metrics.total == 3
    assert metrics.allowed == 2
    assert metrics.denied == 1


def test_denial_rate():
    audit_service = LLMAgentPolicyAuditService()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-1", DENY, "policy-b", "rule-2")
    _record(audit_service, "notebook-1", DENY, "policy-b", "rule-3")

    metrics = LLMAgentPolicyMetricsService(audit_service).summarize("notebook-1")

    assert metrics.denial_rate == pytest.approx(2 / 3)


def test_policy_and_rule_breakdown():
    audit_service = LLMAgentPolicyAuditService()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-1", DENY, "policy-b", "rule-2")

    metrics = LLMAgentPolicyMetricsService(audit_service).summarize("notebook-1")

    assert metrics.by_policy == {
        "policy-a": {"total": 2, "allowed": 2, "denied": 0},
        "policy-b": {"total": 1, "allowed": 0, "denied": 1},
    }
    assert metrics.by_rule == {
        "rule-1": {"total": 2, "allowed": 2, "denied": 0},
        "rule-2": {"total": 1, "allowed": 0, "denied": 1},
    }


def test_exception_counts():
    audit_service = LLMAgentPolicyAuditService()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(
        audit_service, "notebook-1", ALLOW, "policy-b", "rule-2",
        exceptions=[{"exception_id": "exc-1", "policy_id": "policy-b", "reason": "approved"}],
    )

    metrics = LLMAgentPolicyMetricsService(audit_service).summarize("notebook-1")

    assert metrics.total == 2
    assert metrics.exception_assisted == 1


def test_filters_time_range():
    audit_service = LLMAgentPolicyAuditService()
    old = _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1", created_at=NOW - timedelta(days=10))
    recent = _record(audit_service, "notebook-1", DENY, "policy-b", "rule-2", created_at=NOW)

    metrics_service = LLMAgentPolicyMetricsService(audit_service)

    all_time = metrics_service.summarize("notebook-1")
    assert all_time.total == 2

    recent_only = metrics_service.summarize(
        "notebook-1", filters={"start": NOW - timedelta(days=1), "end": NOW + timedelta(days=1)}
    )
    assert recent_only.total == 1
    assert recent_only.denied == 1

    old_only = metrics_service.summarize(
        "notebook-1", filters={"start": NOW - timedelta(days=11), "end": NOW - timedelta(days=9)}
    )
    assert old_only.total == 1
    assert old_only.allowed == 1

    # by_period buckets by calendar day
    assert old.created_at.date().isoformat() in all_time.by_period
    assert recent.created_at.date().isoformat() in all_time.by_period


def test_filters_decision_and_policy():
    audit_service = LLMAgentPolicyAuditService()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-1", DENY, "policy-b", "rule-2")

    metrics_service = LLMAgentPolicyMetricsService(audit_service)

    only_denied = metrics_service.summarize("notebook-1", filters={"decision": DENY})
    assert only_denied.total == 1
    assert only_denied.denied == 1

    only_policy_a = metrics_service.summarize("notebook-1", filters={"policy_id": "policy-a"})
    assert only_policy_a.total == 1
    assert only_policy_a.allowed == 1

    only_rule_2 = metrics_service.summarize("notebook-1", filters={"rule_id": "rule-2"})
    assert only_rule_2.total == 1
    assert only_rule_2.denied == 1


def test_invalid_filters_rejected():
    audit_service = LLMAgentPolicyAuditService()
    metrics_service = LLMAgentPolicyMetricsService(audit_service)

    with pytest.raises(InvalidMetricsFilterError):
        metrics_service.summarize("notebook-1", filters="not-a-dict")

    with pytest.raises(InvalidMetricsFilterError):
        metrics_service.summarize("notebook-1", filters={"start": "not-a-datetime"})

    with pytest.raises(InvalidMetricsFilterError):
        metrics_service.summarize("notebook-1", filters={"start": NOW, "end": NOW - timedelta(days=1)})

    with pytest.raises(InvalidMetricsFilterError):
        metrics_service.summarize("notebook-1", filters={"decision": "MAYBE"})


def test_empty_scope():
    audit_service = LLMAgentPolicyAuditService()
    metrics = LLMAgentPolicyMetricsService(audit_service).summarize("empty-notebook")

    assert metrics.total == 0
    assert metrics.allowed == 0
    assert metrics.denied == 0
    assert metrics.exception_assisted == 0
    assert metrics.denial_rate == 0.0
    assert metrics.by_policy == {}
    assert metrics.by_rule == {}
    assert metrics.by_period == {}


def test_scope_isolation():
    audit_service = LLMAgentPolicyAuditService()
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-1", ALLOW, "policy-a", "rule-1")
    _record(audit_service, "notebook-2", DENY, "policy-a", "rule-1")

    metrics_service = LLMAgentPolicyMetricsService(audit_service)
    notebook_1 = metrics_service.summarize("notebook-1")
    notebook_2 = metrics_service.summarize("notebook-2")

    assert notebook_1.total == 2 and notebook_1.denied == 0
    assert notebook_2.total == 1 and notebook_2.denied == 1


def test_scope_secret_detection():
    audit_service = LLMAgentPolicyAuditService()
    metrics_service = LLMAgentPolicyMetricsService(audit_service)

    with pytest.raises(SecretInScopeError):
        metrics_service.summarize("api_key: sk-abcdefghijklmnopqrstuvwxyz")

    with pytest.raises(ValueError):
        metrics_service.summarize("")


def test_metrics_never_expose_action_payload():
    audit_service = LLMAgentPolicyAuditService()
    _record(audit_service, "notebook-1", DENY, "policy-a", "rule-1")

    metrics = LLMAgentPolicyMetricsService(audit_service).summarize("notebook-1")

    dumped = str(metrics)
    assert "arguments" not in dumped
    assert "topic" not in dumped
