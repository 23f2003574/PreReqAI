from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionAlertRuleService,
    ExecutionAlertService,
    ExecutionAlertSuppressionService,
    ExecutionMetricsService,
    ExecutionObservabilityAlertRule,
    ExecutionObservabilityAlertSuppression,
    ExecutionObservabilityAlertSuppressionError as Error,
)


class _FakeRuntimeService:
    def __init__(self, statuses=None):
        self._statuses = dict(statuses or {"runtime-1": "RUNNING", "runtime-2": "RUNNING"})

    def status(self, runtime_id):
        if runtime_id not in self._statuses:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return self._statuses[runtime_id]


def _future(seconds=60):
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def _past(seconds=60):
    return datetime.now(timezone.utc) - timedelta(seconds=seconds)


class TestExecutionAlertSuppressionService:
    def test_create_and_check_suppression(self):
        service = ExecutionAlertSuppressionService()

        suppression = service.suppress("rule-1", "runtime-1", "known noisy alert", _future())

        assert isinstance(suppression, ExecutionObservabilityAlertSuppression)
        assert suppression.enabled is True
        assert service.is_suppressed("rule-1", "runtime-1") is True
        assert service.active("runtime-1") == (suppression,)

    def test_no_suppression_by_default(self):
        service = ExecutionAlertSuppressionService()

        assert service.is_suppressed("rule-1", "runtime-1") is False
        assert service.active("runtime-1") == ()

    def test_expiry(self):
        service = ExecutionAlertSuppressionService()

        suppression = service.suppress("rule-1", "runtime-1", "temporary noise", _past())

        assert service.is_suppressed("rule-1", "runtime-1") is False
        assert service.active("runtime-1") == ()
        assert service.expired() == (suppression,)

    def test_revocation(self):
        service = ExecutionAlertSuppressionService()

        suppression = service.suppress("rule-1", "runtime-1", "known noisy alert", _future())
        revoked = service.revoke(suppression.suppression_id)

        assert revoked.enabled is False
        assert service.is_suppressed("rule-1", "runtime-1") is False
        assert service.active("runtime-1") == ()

    def test_revocation_is_idempotent(self):
        service = ExecutionAlertSuppressionService()

        suppression = service.suppress("rule-1", "runtime-1", "known noisy alert", _future())

        first = service.revoke(suppression.suppression_id)
        second = service.revoke(suppression.suppression_id)

        assert first == second

    def test_revoke_unknown_suppression_rejection(self):
        service = ExecutionAlertSuppressionService()

        with pytest.raises(Error):
            service.revoke("does-not-exist")

    def test_runtime_isolation(self):
        service = ExecutionAlertSuppressionService()

        service.suppress("rule-1", "runtime-1", "known noisy alert", _future())

        assert service.is_suppressed("rule-1", "runtime-2") is False
        assert service.active("runtime-2") == ()

    def test_rule_isolation_within_runtime(self):
        service = ExecutionAlertSuppressionService()

        service.suppress("rule-1", "runtime-1", "known noisy alert", _future())

        assert service.is_suppressed("rule-2", "runtime-1") is False

    def test_missing_reason_rejection(self):
        service = ExecutionAlertSuppressionService()

        with pytest.raises(Exception):
            service.suppress("rule-1", "runtime-1", "", _future())

        with pytest.raises(Exception):
            service.suppress("rule-1", "runtime-1", None, _future())

    def test_missing_expiry_rejection(self):
        service = ExecutionAlertSuppressionService()

        with pytest.raises(Exception):
            service.suppress("rule-1", "runtime-1", "known noisy alert", None)

        with pytest.raises(Exception):
            service.suppress("rule-1", "runtime-1", "known noisy alert", "tomorrow")

    def test_suppression_does_not_affect_existing_alert_history(self):
        runtime_service = _FakeRuntimeService()
        metrics_service = ExecutionMetricsService(runtime_service)
        alert_rule_service = ExecutionAlertRuleService(metrics_service)
        alert_service = ExecutionAlertService(alert_rule_service, metrics_service)
        suppression_service = ExecutionAlertSuppressionService()

        rule = ExecutionObservabilityAlertRule(
            name="high latency", metric="latency_ms", operator="GT", threshold=100, severity="WARNING"
        )
        alert_rule_service.register(rule)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")

        alert = alert_service.trigger("runtime-1", rule.rule_id)
        history_before = alert_service.history("runtime-1")

        suppression_service.suppress(rule.rule_id, "runtime-1", "known noisy alert", _future())

        history_after = alert_service.history("runtime-1")

        assert history_before == history_after
        assert history_after == (alert,)
        assert alert_service.active("runtime-1") == (alert,)
