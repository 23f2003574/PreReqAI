from datetime import datetime, timezone

import pytest

from backend.llm.security_audit import INPUT, OUTPUT, LLMSecurityAudit
from backend.llm.security_gate import FAILED, PASSED, LLMSecurityGateService, UnknownGateEvaluationError
from backend.llm.security_health import LLMSecurityHealthService
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


def build_gate_service(records, allow_degraded=False):
    fake_audit = FakeSecurityAuditService(records)
    metrics_service = LLMSecurityMetricsService(fake_audit)
    health_service = LLMSecurityHealthService(metrics_service)
    return LLMSecurityGateService(health_service, allow_degraded=allow_degraded)


def test_healthy_passes():
    gate_service = build_gate_service([make_audit("a1", "req-a", INPUT, ALLOW, DAY1)])

    gate = gate_service.evaluate(None, (DAY1, DAY1))

    assert gate.status == PASSED
    assert gate_service.passed(None, (DAY1, DAY1)) is True
    assert gate_service.blocking(None, (DAY1, DAY1)) is False


def test_degraded_result_is_policy_dependent():
    records = [
        make_audit("a1", "req-a", OUTPUT, REDACT, DAY1, policy_ids=("p1",), finding_types=("SECRETS",))
    ]

    strict_gate_service = build_gate_service(records, allow_degraded=False)
    strict = strict_gate_service.evaluate(None, (DAY1, DAY1))
    assert strict.status == FAILED

    permissive_gate_service = build_gate_service(records, allow_degraded=True)
    permissive = permissive_gate_service.evaluate(None, (DAY1, DAY1))
    assert permissive.status == PASSED


def test_critical_fails():
    gate_service = build_gate_service(
        [make_audit("a1", "req-a", OUTPUT, BLOCK, DAY1, finding_types=("UNSAFE_INSTRUCTION",))]
    )

    gate = gate_service.evaluate(None, (DAY1, DAY1))

    assert gate.status == FAILED
    assert gate_service.blocking(None, (DAY1, DAY1)) is True


def test_blocking_finding_fails_independent_of_overall_status():
    gate_service = build_gate_service(
        [make_audit("a1", "req-a", INPUT, BLOCK, DAY1, finding_types=("TOOL_BOUNDARY_BYPASS",))]
    )

    gate = gate_service.evaluate(None, (DAY1, DAY1))

    assert gate.status == FAILED
    assert any(finding["check"] == "blocking_events" for finding in gate.findings)


def test_unknown_data_does_not_silently_pass():
    gate_service = build_gate_service([make_audit("a1", "req-a", INPUT, ALLOW, DAY1)])

    gate = gate_service.evaluate(None, (DAY3, DAY4))

    assert gate.status == FAILED
    assert gate_service.blocking(None, (DAY3, DAY4)) is True


def test_period_and_scope_isolation():
    records = [
        make_audit("a1", "req-a", INPUT, ALLOW, DAY1),
        make_audit("a2", "req-b", OUTPUT, BLOCK, DAY3, finding_types=("UNSAFE_INSTRUCTION",)),
    ]
    gate_service = build_gate_service(records)

    scope_a = gate_service.evaluate("req-a", (DAY1, DAY4))
    scope_b = gate_service.evaluate("req-b", (DAY1, DAY4))
    narrowed = gate_service.evaluate(None, (DAY1, DAY1))

    assert scope_a.status == PASSED
    assert scope_b.status == FAILED
    assert narrowed.status == PASSED

    with pytest.raises(UnknownGateEvaluationError):
        gate_service.passed("req-a", (DAY2, DAY3))


def test_deterministic_result():
    gate_service = build_gate_service(
        [make_audit("a1", "req-a", OUTPUT, REDACT, DAY1, finding_types=("SECRETS",))]
    )

    first = gate_service.evaluate(None, (DAY1, DAY1))
    second = gate_service.evaluate(None, (DAY1, DAY1))

    assert first.status == second.status
    assert first.findings == second.findings
    assert first.scope == second.scope
