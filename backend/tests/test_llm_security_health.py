from datetime import datetime, timezone

from backend.llm.security_audit import INPUT, OUTPUT, LLMSecurityAudit
from backend.llm.security_health import CRITICAL, DEGRADED, HEALTHY, UNKNOWN, LLMSecurityHealthService
from backend.llm.security_metrics import LLMSecurityMetricsService
from backend.llm.security_policy import ALLOW, BLOCK, REDACT

DAY1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
DAY2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
DAY3 = datetime(2026, 1, 3, tzinfo=timezone.utc)
DAY4 = datetime(2026, 1, 4, tzinfo=timezone.utc)


class FakeSecurityAuditService:
    def __init__(self, records):
        self._records = records

    def records(self, scope=None):
        if scope is None:
            return tuple(self._records)
        return tuple(r for r in self._records if r.request_id == scope)


def make_audit(audit_id, request_id, direction, decision, created_at, policy_ids=(), finding_types=()):
    return LLMSecurityAudit(
        audit_id=audit_id,
        request_id=request_id,
        direction=direction,
        decision=decision,
        policy_ids=tuple(policy_ids),
        finding_types=tuple(finding_types),
        created_at=created_at,
    )


def build_health(records):
    fake_audit = FakeSecurityAuditService(records)
    metrics_service = LLMSecurityMetricsService(fake_audit)
    return LLMSecurityHealthService(metrics_service)


def test_healthy_state():
    health = build_health(
        [
            make_audit("a1", "req-a", INPUT, ALLOW, DAY1),
            make_audit("a2", "req-a", OUTPUT, ALLOW, DAY1),
        ]
    )

    assessment = health.assess(None, (DAY1, DAY1))

    assert assessment["status"] == HEALTHY
    assert assessment["findings"] == [
        {"check": "data_sufficiency", "severity": HEALTHY, "detail": "2 security decision(s) recorded"}
    ]


def test_degraded_state():
    health = build_health(
        [make_audit("a1", "req-a", OUTPUT, REDACT, DAY1, policy_ids=("p1",), finding_types=("SECRETS",))]
    )

    status = health.status(None, (DAY1, DAY1))
    findings = health.findings(None, (DAY1, DAY1))

    assert status == DEGRADED
    assert any(f["check"] == "redaction_events" and f["severity"] == DEGRADED for f in findings)
    assert any(f["check"] == "finding:SECRETS" for f in findings)


def test_critical_state():
    health = build_health(
        [make_audit("a1", "req-a", INPUT, BLOCK, DAY1, finding_types=("UNSAFE_INSTRUCTION",))]
    )

    status = health.status(None, (DAY1, DAY1))
    findings = health.findings(None, (DAY1, DAY1))

    assert status == CRITICAL
    assert any(f["check"] == "blocking_events" and f["severity"] == CRITICAL for f in findings)
    assert any(f["check"] == "finding:UNSAFE_INSTRUCTION" and f["severity"] == CRITICAL for f in findings)


def test_insufficient_data_is_unknown():
    health = build_health([make_audit("a1", "req-a", INPUT, ALLOW, DAY1)])

    assessment = health.assess(None, (DAY3, DAY4))

    assert assessment["status"] == UNKNOWN
    assert assessment["findings"] == [
        {
            "check": "data_sufficiency",
            "severity": UNKNOWN,
            "detail": "no security-audit records for this scope/period",
        }
    ]


def test_multiple_findings_resolve_to_the_most_severe():
    health = build_health(
        [
            make_audit("a1", "req-a", INPUT, ALLOW, DAY1),
            make_audit("a2", "req-b", OUTPUT, REDACT, DAY1, policy_ids=("p1",), finding_types=("SECRETS",)),
            make_audit("a3", "req-c", INPUT, BLOCK, DAY1, finding_types=("TOOL_BOUNDARY_BYPASS",)),
        ]
    )

    assessment = health.assess(None, (DAY1, DAY1))

    assert assessment["status"] == CRITICAL
    checks = {f["check"] for f in assessment["findings"]}
    assert {"data_sufficiency", "blocking_events", "redaction_events", "finding:SECRETS", "finding:TOOL_BOUNDARY_BYPASS"} <= checks
    assert len(assessment["findings"]) > 1


def test_period_filtering_changes_the_status():
    health = build_health(
        [
            make_audit("a1", "req-a", INPUT, ALLOW, DAY1),
            make_audit("a2", "req-b", OUTPUT, BLOCK, DAY3, finding_types=("UNSAFE_INSTRUCTION",)),
        ]
    )

    narrowed = health.status(None, (DAY1, DAY1))
    full = health.status(None, (DAY1, DAY3))

    assert narrowed == HEALTHY
    assert full == CRITICAL


def test_status_is_deterministic():
    health = build_health(
        [
            make_audit("a1", "req-a", INPUT, ALLOW, DAY1),
            make_audit("a2", "req-b", OUTPUT, REDACT, DAY1, finding_types=("SECRETS",)),
        ]
    )

    first = health.assess(None, (DAY1, DAY1))
    second = health.assess(None, (DAY1, DAY1))
    first.pop("assessed_at")
    second.pop("assessed_at")

    assert first == second
