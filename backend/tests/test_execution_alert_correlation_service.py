import pytest

from backend.session import (
    ExecutionAlertCorrelationService,
    ExecutionAlertRuleService,
    ExecutionAlertService,
    ExecutionMetricsService,
    ExecutionObservabilityAlertCorrelation,
    ExecutionObservabilityAlertCorrelationError as Error,
    ExecutionObservabilityAlertRule,
)


class _FakeRuntimeService:
    def __init__(self, statuses=None):
        self._statuses = dict(
            statuses or {"runtime-1": "RUNNING", "runtime-2": "RUNNING", "runtime-3": "RUNNING"}
        )

    def status(self, runtime_id):
        if runtime_id not in self._statuses:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return self._statuses[runtime_id]


def _build():
    runtime_service = _FakeRuntimeService()
    metrics_service = ExecutionMetricsService(runtime_service)
    alert_rule_service = ExecutionAlertRuleService(metrics_service)
    alert_service = ExecutionAlertService(alert_rule_service, metrics_service)
    correlation_service = ExecutionAlertCorrelationService(alert_service)

    return metrics_service, alert_rule_service, alert_service, correlation_service


def _register_rule(alert_rule_service, metric="latency_ms", severity="WARNING"):
    rule = ExecutionObservabilityAlertRule(
        name=f"{metric} rule", metric=metric, operator="GT", threshold=100, severity=severity
    )
    alert_rule_service.register(rule)

    return rule


class TestExecutionAlertCorrelationService:
    def test_correlate_alerts(self):
        metrics_service, alert_rule_service, alert_service, correlation_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        metrics_service.record("runtime-2", "latency_ms", 150, "ms")

        first = alert_service.trigger("runtime-1", rule.rule_id)
        second = alert_service.trigger("runtime-2", rule.rule_id)

        correlation = correlation_service.correlate([first.alert_id, second.alert_id])

        assert isinstance(correlation, ExecutionObservabilityAlertCorrelation)
        assert set(correlation.alert_ids) == {first.alert_id, second.alert_id}
        assert set(correlation.runtime_ids) == {"runtime-1", "runtime-2"}
        assert correlation.status == "ACTIVE"

    def test_root_selection(self):
        metrics_service, alert_rule_service, alert_service, correlation_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        first = alert_service.trigger("runtime-1", rule.rule_id)

        metrics_service.record("runtime-2", "latency_ms", 150, "ms")
        second = alert_service.trigger("runtime-2", rule.rule_id)

        correlation = correlation_service.correlate([second.alert_id, first.alert_id])

        assert correlation.root_alert_id == first.alert_id
        assert correlation_service.root(correlation.correlation_id).alert_id == first.alert_id

    def test_duplicate_membership_within_call(self):
        metrics_service, alert_rule_service, alert_service, correlation_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert = alert_service.trigger("runtime-1", rule.rule_id)

        with pytest.raises(Error):
            correlation_service.correlate([alert.alert_id, alert.alert_id])

    def test_duplicate_membership_across_correlations(self):
        metrics_service, alert_rule_service, alert_service, correlation_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        metrics_service.record("runtime-2", "latency_ms", 150, "ms")
        metrics_service.record("runtime-3", "latency_ms", 150, "ms")

        first = alert_service.trigger("runtime-1", rule.rule_id)
        second = alert_service.trigger("runtime-2", rule.rule_id)
        third = alert_service.trigger("runtime-3", rule.rule_id)

        correlation_service.correlate([first.alert_id, second.alert_id])

        with pytest.raises(Error):
            correlation_service.correlate([first.alert_id, third.alert_id])

    def test_incompatible_alerts_rejection(self):
        metrics_service, alert_rule_service, alert_service, correlation_service = _build()

        latency_rule = _register_rule(alert_rule_service, metric="latency_ms")
        memory_rule = _register_rule(alert_rule_service, metric="memory_mb")

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        metrics_service.record("runtime-2", "memory_mb", 150, "mb")

        latency_alert = alert_service.trigger("runtime-1", latency_rule.rule_id)
        memory_alert = alert_service.trigger("runtime-2", memory_rule.rule_id)

        with pytest.raises(Error):
            correlation_service.correlate([latency_alert.alert_id, memory_alert.alert_id])

    def test_correlate_too_few_alerts_rejection(self):
        metrics_service, alert_rule_service, alert_service, correlation_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert = alert_service.trigger("runtime-1", rule.rule_id)

        with pytest.raises(Error):
            correlation_service.correlate([alert.alert_id])

    def test_resolution(self):
        metrics_service, alert_rule_service, alert_service, correlation_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        metrics_service.record("runtime-2", "latency_ms", 150, "ms")

        first = alert_service.trigger("runtime-1", rule.rule_id)
        second = alert_service.trigger("runtime-2", rule.rule_id)

        correlation = correlation_service.correlate([first.alert_id, second.alert_id])
        resolved = correlation_service.resolve(correlation.correlation_id)

        assert resolved.status == "RESOLVED"

        # Members are freed once the correlation resolves.
        new_correlation = correlation_service.correlate([first.alert_id, second.alert_id])
        assert new_correlation.status == "ACTIVE"

    def test_resolve_is_idempotent(self):
        metrics_service, alert_rule_service, alert_service, correlation_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        metrics_service.record("runtime-2", "latency_ms", 150, "ms")

        first = alert_service.trigger("runtime-1", rule.rule_id)
        second = alert_service.trigger("runtime-2", rule.rule_id)

        correlation = correlation_service.correlate([first.alert_id, second.alert_id])

        first_result = correlation_service.resolve(correlation.correlation_id)
        second_result = correlation_service.resolve(correlation.correlation_id)

        assert first_result == second_result

    def test_resolving_root_alert_resolves_correlation(self):
        metrics_service, alert_rule_service, alert_service, correlation_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        first = alert_service.trigger("runtime-1", rule.rule_id)

        metrics_service.record("runtime-2", "latency_ms", 150, "ms")
        second = alert_service.trigger("runtime-2", rule.rule_id)

        correlation = correlation_service.correlate([first.alert_id, second.alert_id])
        assert correlation.root_alert_id == first.alert_id

        alert_service.resolve(first.alert_id)

        assert correlation_service.alerts(correlation.correlation_id)
        resolved = correlation_service.resolve(correlation.correlation_id)

        assert resolved.status == "RESOLVED"

    def test_correlation_lookup(self):
        metrics_service, alert_rule_service, alert_service, correlation_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        metrics_service.record("runtime-2", "latency_ms", 150, "ms")

        first = alert_service.trigger("runtime-1", rule.rule_id)
        second = alert_service.trigger("runtime-2", rule.rule_id)

        correlation = correlation_service.correlate([first.alert_id, second.alert_id])

        alerts = correlation_service.alerts(correlation.correlation_id)

        assert alerts == (first, second)

    def test_unknown_correlation_rejection(self):
        _, _, _, correlation_service = _build()

        with pytest.raises(Error):
            correlation_service.root("does-not-exist")

        with pytest.raises(Error):
            correlation_service.alerts("does-not-exist")

        with pytest.raises(Error):
            correlation_service.resolve("does-not-exist")

    def test_unknown_alert_rejection(self):
        _, _, _, correlation_service = _build()

        with pytest.raises(Error):
            correlation_service.correlate(["does-not-exist", "also-missing"])
