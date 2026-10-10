import pytest

from backend.session import (
    ExecutionAlertEscalationService,
    ExecutionAlertRuleService,
    ExecutionAlertService,
    ExecutionMetricsService,
    ExecutionObservabilityAlertRule,
    ExecutionObservabilityEscalation,
    ExecutionObservabilityEscalationError as Error,
)


class _FakeRuntimeService:
    def __init__(self, statuses=None):
        self._statuses = dict(statuses or {"runtime-1": "RUNNING"})

    def status(self, runtime_id):
        if runtime_id not in self._statuses:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return self._statuses[runtime_id]


def _build():
    runtime_service = _FakeRuntimeService()
    metrics_service = ExecutionMetricsService(runtime_service)
    alert_rule_service = ExecutionAlertRuleService(metrics_service)
    alert_service = ExecutionAlertService(alert_rule_service, metrics_service)
    escalation_service = ExecutionAlertEscalationService(alert_service)

    return metrics_service, alert_rule_service, alert_service, escalation_service


def _trigger_alert(metrics_service, alert_rule_service, alert_service, severity="WARNING"):
    rule = ExecutionObservabilityAlertRule(
        name="high latency", metric="latency_ms", operator="GT", threshold=100, severity=severity
    )
    alert_rule_service.register(rule)
    metrics_service.record("runtime-1", "latency_ms", 150, "ms")

    return alert_service.trigger("runtime-1", rule.rule_id)


class TestExecutionAlertEscalationService:
    def test_escalation_trigger(self):
        metrics_service, alert_rule_service, alert_service, escalation_service = _build()

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, severity="WARNING")

        escalation = escalation_service.escalate(alert.alert_id)

        assert isinstance(escalation, ExecutionObservabilityEscalation)
        assert escalation.alert_id == alert.alert_id
        assert escalation.status == "ACTIVE"
        assert escalation_service.level(alert.alert_id) == escalation.level

    def test_severity_based_escalation(self):
        metrics_service, alert_rule_service, alert_service, escalation_service = _build()

        warning_alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, severity="WARNING")
        assert escalation_service.evaluate(warning_alert.alert_id) == "WARNING"

        error_alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, severity="ERROR")
        assert escalation_service.evaluate(error_alert.alert_id) == "CRITICAL"

        warning_escalation = escalation_service.escalate(warning_alert.alert_id)
        error_escalation = escalation_service.escalate(error_alert.alert_id)

        assert warning_escalation.level == "WARNING"
        assert error_escalation.level == "CRITICAL"

    def test_repeated_escalation_rejection(self):
        metrics_service, alert_rule_service, alert_service, escalation_service = _build()

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, severity="WARNING")
        escalation_service.escalate(alert.alert_id)

        with pytest.raises(Error):
            escalation_service.escalate(alert.alert_id)

    def test_resolution_propagation(self):
        metrics_service, alert_rule_service, alert_service, escalation_service = _build()

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, severity="WARNING")
        escalation = escalation_service.escalate(alert.alert_id)

        alert_service.resolve(alert.alert_id)

        assert escalation_service.level(alert.alert_id) is None
        assert escalation_service.history(alert.alert_id)[0].status == "RESOLVED"

        with pytest.raises(Error):
            escalation_service.escalate(alert.alert_id)

    def test_escalation_history(self):
        metrics_service, alert_rule_service, alert_service, escalation_service = _build()

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, severity="WARNING")
        first = escalation_service.escalate(alert.alert_id)
        resolved = escalation_service.resolve(first.escalation_id)

        assert escalation_service.history(alert.alert_id) == (resolved,)

    def test_terminal_alert_handling(self):
        metrics_service, alert_rule_service, alert_service, escalation_service = _build()

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, severity="WARNING")
        alert_service.resolve(alert.alert_id)

        assert escalation_service.evaluate(alert.alert_id) is None

        with pytest.raises(Error):
            escalation_service.escalate(alert.alert_id)

    def test_non_escalatable_severity_rejection(self):
        metrics_service, alert_rule_service, alert_service, escalation_service = _build()

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, severity="INFO")

        assert escalation_service.evaluate(alert.alert_id) is None

        with pytest.raises(Error):
            escalation_service.escalate(alert.alert_id)

    def test_resolve_is_idempotent(self):
        metrics_service, alert_rule_service, alert_service, escalation_service = _build()

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, severity="WARNING")
        escalation = escalation_service.escalate(alert.alert_id)

        first = escalation_service.resolve(escalation.escalation_id)
        second = escalation_service.resolve(escalation.escalation_id)

        assert first == second
        assert escalation_service.level(alert.alert_id) is None

    def test_resolve_unknown_escalation_rejection(self):
        _, _, _, escalation_service = _build()

        with pytest.raises(Error):
            escalation_service.resolve("does-not-exist")

    def test_unknown_alert_rejection(self):
        _, _, _, escalation_service = _build()

        with pytest.raises(Error):
            escalation_service.escalate("does-not-exist")
