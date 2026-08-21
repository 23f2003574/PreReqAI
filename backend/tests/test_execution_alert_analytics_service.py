import pytest

from backend.session import (
    ExecutionAlertAnalytics,
    ExecutionAlertAnalyticsError as Error,
    ExecutionAlertAnalyticsService,
    ExecutionAlertDeduplicationService,
    ExecutionAlertRuleService,
    ExecutionAlertService,
    ExecutionMetricsService,
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
    dedup_service = ExecutionAlertDeduplicationService()
    analytics_service = ExecutionAlertAnalyticsService(alert_service, dedup_service)

    return metrics_service, alert_rule_service, alert_service, analytics_service


def _register_rule(alert_rule_service, metric="latency_ms", severity="WARNING", threshold=100):
    rule = ExecutionObservabilityAlertRule(
        name=f"{metric} rule", metric=metric, operator="GT", threshold=threshold, severity=severity
    )
    alert_rule_service.register(rule)

    return rule


class TestExecutionAlertAnalyticsService:
    def test_alert_totals(self):
        metrics_service, alert_rule_service, alert_service, analytics_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert_service.trigger("runtime-1", rule.rule_id)

        metrics_service.record("runtime-1", "latency_ms", 200, "ms")
        alert_service.trigger("runtime-1", rule.rule_id)

        analytics = analytics_service.generate("runtime-1")

        assert isinstance(analytics, ExecutionAlertAnalytics)
        assert analytics.runtime_id == "runtime-1"
        assert analytics.total_alerts == 2

    def test_severity_breakdown(self):
        metrics_service, alert_rule_service, alert_service, analytics_service = _build()

        warning_rule = _register_rule(alert_rule_service, metric="latency_ms", severity="WARNING")
        error_rule = _register_rule(alert_rule_service, metric="memory_mb", severity="ERROR")

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert_service.trigger("runtime-1", warning_rule.rule_id)

        metrics_service.record("runtime-1", "memory_mb", 150, "mb")
        alert_service.trigger("runtime-1", error_rule.rule_id)

        breakdown = analytics_service.severity_breakdown("runtime-1")

        assert breakdown == {"WARNING": 1, "ERROR": 1}

        analytics = analytics_service.generate("runtime-1")
        assert analytics.critical_count == 1

    def test_open_resolved_counts(self):
        metrics_service, alert_rule_service, alert_service, analytics_service = _build()

        rule = _register_rule(alert_rule_service)

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        first = alert_service.trigger("runtime-1", rule.rule_id)

        metrics_service.record("runtime-1", "latency_ms", 200, "ms")
        alert_service.trigger("runtime-1", rule.rule_id)

        alert_service.resolve(first.alert_id)

        analytics = analytics_service.generate("runtime-1")

        assert analytics.open_alerts == 1
        assert analytics.resolved_alerts == 1
        assert analytics.total_alerts == 2

    def test_recurrence_calculation(self):
        metrics_service, alert_rule_service, alert_service, analytics_service = _build()

        rule = _register_rule(alert_rule_service)

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert_service.trigger("runtime-1", rule.rule_id)

        metrics_service.record("runtime-1", "latency_ms", 200, "ms")
        alert_service.trigger("runtime-1", rule.rule_id)

        metrics_service.record("runtime-1", "latency_ms", 250, "ms")
        alert_service.trigger("runtime-1", rule.rule_id)

        stats = analytics_service.recurrence("runtime-1")

        assert stats["total_alerts"] == 3
        assert stats["distinct_conditions"] == 1
        assert stats["recurrence_rate"] == pytest.approx(2 / 3)

        analytics = analytics_service.generate("runtime-1")
        assert analytics.recurrence_rate == pytest.approx(2 / 3)

    def test_deduplicated_counting_across_conditions(self):
        metrics_service, alert_rule_service, alert_service, analytics_service = _build()

        latency_rule = _register_rule(alert_rule_service, metric="latency_ms")
        memory_rule = _register_rule(alert_rule_service, metric="memory_mb")

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert_service.trigger("runtime-1", latency_rule.rule_id)
        metrics_service.record("runtime-1", "latency_ms", 200, "ms")
        alert_service.trigger("runtime-1", latency_rule.rule_id)

        metrics_service.record("runtime-1", "memory_mb", 150, "mb")
        alert_service.trigger("runtime-1", memory_rule.rule_id)

        stats = analytics_service.recurrence("runtime-1")

        assert stats["total_alerts"] == 3
        assert stats["distinct_conditions"] == 2
        assert stats["recurrence_rate"] == pytest.approx(1 / 3)

    def test_empty_history(self):
        _, _, _, analytics_service = _build()

        analytics = analytics_service.generate("runtime-2")

        assert analytics.total_alerts == 0
        assert analytics.open_alerts == 0
        assert analytics.resolved_alerts == 0
        assert analytics.critical_count == 0
        assert analytics.recurrence_rate == 0.0
        assert analytics_service.severity_breakdown("runtime-2") == {}
        assert analytics_service.trend("runtime-2") == ()

    def test_trend_is_chronological(self):
        metrics_service, alert_rule_service, alert_service, analytics_service = _build()

        rule = _register_rule(alert_rule_service)

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        first = alert_service.trigger("runtime-1", rule.rule_id)

        metrics_service.record("runtime-1", "latency_ms", 200, "ms")
        second = alert_service.trigger("runtime-1", rule.rule_id)

        trend = analytics_service.trend("runtime-1")

        assert [entry["triggered_at"] for entry in trend] == [first.triggered_at, second.triggered_at]

    def test_deterministic_output(self):
        metrics_service, alert_rule_service, alert_service, analytics_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert_service.trigger("runtime-1", rule.rule_id)

        first = analytics_service.recurrence("runtime-1")
        second = analytics_service.recurrence("runtime-1")
        assert first == second

        first_breakdown = analytics_service.severity_breakdown("runtime-1")
        second_breakdown = analytics_service.severity_breakdown("runtime-1")
        assert first_breakdown == second_breakdown

    def test_generate_does_not_mutate_source_records(self):
        metrics_service, alert_rule_service, alert_service, analytics_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert_service.trigger("runtime-1", rule.rule_id)

        analytics_service.generate("runtime-1")

        assert len(alert_service.history("runtime-1")) == 1

    def test_blank_runtime_id_rejection(self):
        _, _, _, analytics_service = _build()

        with pytest.raises(Error):
            analytics_service.generate("")
