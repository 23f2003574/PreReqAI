import pytest

from backend.session import (
    ExecutionAlertRuleService,
    ExecutionMetricsService,
    ExecutionObservabilityAlertRule,
    ExecutionObservabilityAlertRuleError as Error,
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
    alert_service = ExecutionAlertRuleService(metrics_service)

    return metrics_service, alert_service


class TestExecutionAlertRuleService:
    def test_register_and_evaluate(self):
        metrics_service, alert_service = _build()

        rule = ExecutionObservabilityAlertRule(
            name="high latency",
            metric="latency_ms",
            operator="GT",
            threshold=100,
            severity="WARNING",
        )
        alert_service.register(rule)

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")

        assert alert_service.evaluate("runtime-1") == (rule,)

    def test_threshold_matching(self):
        metrics_service, alert_service = _build()

        rule = ExecutionObservabilityAlertRule(
            name="high latency", metric="latency_ms", operator="GT", threshold=100, severity="WARNING"
        )
        alert_service.register(rule)

        metrics_service.record("runtime-1", "latency_ms", 50, "ms")
        assert alert_service.evaluate("runtime-1") == ()

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        assert alert_service.evaluate("runtime-1") == (rule,)

    @pytest.mark.parametrize(
        "operator, value, threshold, expected",
        [
            ("GT", 10, 5, True),
            ("GT", 5, 5, False),
            ("GTE", 5, 5, True),
            ("GTE", 4, 5, False),
            ("LT", 4, 5, True),
            ("LT", 5, 5, False),
            ("LTE", 5, 5, True),
            ("LTE", 6, 5, False),
            ("EQ", 5, 5, True),
            ("EQ", 6, 5, False),
        ],
    )
    def test_operator_behavior(self, operator, value, threshold, expected):
        metrics_service, alert_service = _build()

        rule = ExecutionObservabilityAlertRule(
            name="rule", metric="metric_a", operator=operator, threshold=threshold, severity="INFO"
        )
        alert_service.register(rule)

        metrics_service.record("runtime-1", "metric_a", value, "unit")

        triggered = alert_service.evaluate("runtime-1")

        assert (rule in triggered) is expected

    def test_multiple_alerts(self):
        metrics_service, alert_service = _build()

        latency_rule = ExecutionObservabilityAlertRule(
            name="high latency", metric="latency_ms", operator="GT", threshold=100, severity="WARNING"
        )
        memory_rule = ExecutionObservabilityAlertRule(
            name="high memory", metric="memory_mb", operator="GTE", threshold=512, severity="ERROR"
        )
        alert_service.register(latency_rule)
        alert_service.register(memory_rule)

        metrics_service.record("runtime-1", "latency_ms", 200, "ms")
        metrics_service.record("runtime-1", "memory_mb", 512, "mb")

        triggered = alert_service.evaluate("runtime-1")

        assert set(triggered) == {latency_rule, memory_rule}

    def test_disabled_rule_ignored(self):
        metrics_service, alert_service = _build()

        rule = ExecutionObservabilityAlertRule(
            name="high latency", metric="latency_ms", operator="GT", threshold=100, severity="WARNING"
        )
        alert_service.register(rule)
        metrics_service.record("runtime-1", "latency_ms", 200, "ms")

        disabled = alert_service.disable(rule.rule_id)

        assert disabled.enabled is False
        assert alert_service.evaluate("runtime-1") == ()
        assert alert_service.violations("runtime-1") == ()

    def test_disable_is_idempotent(self):
        _, alert_service = _build()

        rule = ExecutionObservabilityAlertRule(
            name="high latency", metric="latency_ms", operator="GT", threshold=100, severity="WARNING"
        )
        alert_service.register(rule)

        first = alert_service.disable(rule.rule_id)
        second = alert_service.disable(rule.rule_id)

        assert first == second

    def test_disable_unknown_rule_rejection(self):
        _, alert_service = _build()

        with pytest.raises(Error):
            alert_service.disable("does-not-exist")

    def test_invalid_threshold_rejection(self):
        with pytest.raises(Exception):
            ExecutionObservabilityAlertRule(
                name="bad rule", metric="latency_ms", operator="GT", threshold="high", severity="WARNING"
            )

    def test_invalid_operator_rejection(self):
        with pytest.raises(Exception):
            ExecutionObservabilityAlertRule(
                name="bad rule", metric="latency_ms", operator="ABOVE", threshold=10, severity="WARNING"
            )

    def test_register_non_rule_rejection(self):
        _, alert_service = _build()

        with pytest.raises(Error):
            alert_service.register({"not": "a rule"})

    def test_rule_with_no_recorded_metric_is_skipped(self):
        _, alert_service = _build()

        rule = ExecutionObservabilityAlertRule(
            name="high latency", metric="latency_ms", operator="GT", threshold=100, severity="WARNING"
        )
        alert_service.register(rule)

        assert alert_service.evaluate("runtime-1") == ()

    def test_rules_lists_registered_rules(self):
        _, alert_service = _build()

        first = ExecutionObservabilityAlertRule(
            name="a", metric="latency_ms", operator="GT", threshold=1, severity="INFO"
        )
        second = ExecutionObservabilityAlertRule(
            name="b", metric="memory_mb", operator="GT", threshold=1, severity="INFO"
        )
        alert_service.register(first)
        alert_service.register(second)

        assert alert_service.rules() == (first, second)
