import pytest

from backend.session import (
    ExecutionAlertRuleService,
    ExecutionAlertService,
    ExecutionMetricsService,
    ExecutionObservabilityAlert,
    ExecutionObservabilityAlertError as Error,
    ExecutionObservabilityAlertRule,
)


class _FakeRuntimeService:
    def __init__(self, statuses=None):
        self._statuses = dict(statuses or {"runtime-1": "RUNNING", "runtime-2": "RUNNING"})

    def status(self, runtime_id):
        if runtime_id not in self._statuses:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return self._statuses[runtime_id]


def _build():
    runtime_service = _FakeRuntimeService()
    metrics_service = ExecutionMetricsService(runtime_service)
    alert_rule_service = ExecutionAlertRuleService(metrics_service)
    alert_service = ExecutionAlertService(alert_rule_service, metrics_service)

    return metrics_service, alert_rule_service, alert_service


def _high_latency_rule():
    return ExecutionObservabilityAlertRule(
        name="high latency", metric="latency_ms", operator="GT", threshold=100, severity="WARNING"
    )


class TestExecutionAlertService:
    def test_trigger_alert(self):
        metrics_service, alert_rule_service, alert_service = _build()

        rule = _high_latency_rule()
        alert_rule_service.register(rule)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")

        alert = alert_service.trigger("runtime-1", rule.rule_id)

        assert isinstance(alert, ExecutionObservabilityAlert)
        assert alert.rule_id == rule.rule_id
        assert alert.runtime_id == "runtime-1"
        assert alert.severity == "WARNING"
        assert alert.value == 150
        assert alert.status == "OPEN"
        assert alert.resolved_at is None

    def test_only_triggered_rules_create_alerts(self):
        metrics_service, alert_rule_service, alert_service = _build()

        rule = _high_latency_rule()
        alert_rule_service.register(rule)
        metrics_service.record("runtime-1", "latency_ms", 50, "ms")

        with pytest.raises(Error):
            alert_service.trigger("runtime-1", rule.rule_id)

    def test_trigger_unknown_rule_rejection(self):
        _, _, alert_service = _build()

        with pytest.raises(Error):
            alert_service.trigger("runtime-1", "does-not-exist")

    def test_active_lookup(self):
        metrics_service, alert_rule_service, alert_service = _build()

        rule = _high_latency_rule()
        alert_rule_service.register(rule)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")

        alert = alert_service.trigger("runtime-1", rule.rule_id)

        assert alert_service.active("runtime-1") == (alert,)

    def test_resolve(self):
        metrics_service, alert_rule_service, alert_service = _build()

        rule = _high_latency_rule()
        alert_rule_service.register(rule)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")

        alert = alert_service.trigger("runtime-1", rule.rule_id)
        resolved = alert_service.resolve(alert.alert_id)

        assert resolved.alert_id == alert.alert_id
        assert resolved.status == "RESOLVED"
        assert resolved.resolved_at is not None
        assert alert_service.active("runtime-1") == ()

    def test_repeated_resolution_is_idempotent(self):
        metrics_service, alert_rule_service, alert_service = _build()

        rule = _high_latency_rule()
        alert_rule_service.register(rule)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")

        alert = alert_service.trigger("runtime-1", rule.rule_id)

        first = alert_service.resolve(alert.alert_id)
        second = alert_service.resolve(alert.alert_id)

        assert first == second

    def test_resolve_unknown_alert_rejection(self):
        _, _, alert_service = _build()

        with pytest.raises(Error):
            alert_service.resolve("does-not-exist")

    def test_history_ordering(self):
        metrics_service, alert_rule_service, alert_service = _build()

        rule = _high_latency_rule()
        alert_rule_service.register(rule)

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        first = alert_service.trigger("runtime-1", rule.rule_id)

        metrics_service.record("runtime-1", "latency_ms", 200, "ms")
        second = alert_service.trigger("runtime-1", rule.rule_id)

        assert alert_service.history("runtime-1") == (first, second)

    def test_runtime_isolation(self):
        metrics_service, alert_rule_service, alert_service = _build()

        rule = _high_latency_rule()
        alert_rule_service.register(rule)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        metrics_service.record("runtime-2", "latency_ms", 150, "ms")

        alert = alert_service.trigger("runtime-1", rule.rule_id)

        assert alert_service.history("runtime-2") == ()
        assert alert_service.active("runtime-2") == ()
        assert alert_service.history("runtime-1") == (alert,)

    def test_rule_isolation(self):
        metrics_service, alert_rule_service, alert_service = _build()

        latency_rule = _high_latency_rule()
        memory_rule = ExecutionObservabilityAlertRule(
            name="high memory", metric="memory_mb", operator="GTE", threshold=512, severity="ERROR"
        )
        alert_rule_service.register(latency_rule)
        alert_rule_service.register(memory_rule)

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        metrics_service.record("runtime-1", "memory_mb", 512, "mb")

        latency_alert = alert_service.trigger("runtime-1", latency_rule.rule_id)
        memory_alert = alert_service.trigger("runtime-1", memory_rule.rule_id)

        assert latency_alert.rule_id != memory_alert.rule_id
        assert set(alert_service.history("runtime-1")) == {latency_alert, memory_alert}

    def test_preserves_original_metric_value_after_metric_changes(self):
        metrics_service, alert_rule_service, alert_service = _build()

        rule = _high_latency_rule()
        alert_rule_service.register(rule)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")

        alert = alert_service.trigger("runtime-1", rule.rule_id)

        metrics_service.record("runtime-1", "latency_ms", 999, "ms")

        assert alert.value == 150
        assert alert_service.history("runtime-1")[0].value == 150
