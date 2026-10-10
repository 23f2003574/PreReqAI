from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionAlertRoutingService,
    ExecutionAlertRuleService,
    ExecutionAlertService,
    ExecutionMetricsService,
    ExecutionObservabilityAlertRoute,
    ExecutionObservabilityAlertRouteError as Error,
    ExecutionObservabilityAlertRule,
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
    routing_service = ExecutionAlertRoutingService(alert_service)

    return metrics_service, alert_rule_service, alert_service, routing_service


def _trigger_alert(metrics_service, alert_rule_service, alert_service, severity, metric="latency_ms"):
    rule = ExecutionObservabilityAlertRule(
        name=f"{metric} rule", metric=metric, operator="GT", threshold=100, severity=severity
    )
    alert_rule_service.register(rule)
    metrics_service.record("runtime-1", metric, 150, "ms")

    return alert_service.trigger("runtime-1", rule.rule_id)


class TestExecutionAlertRoutingService:
    def test_register_and_resolve(self):
        metrics_service, alert_rule_service, alert_service, routing_service = _build()

        route = ExecutionObservabilityAlertRoute(severity="WARNING", destination="slack:#alerts")
        routing_service.register(route)

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, "WARNING")

        assert routing_service.resolve(alert.alert_id) == route

    def test_severity_matching(self):
        metrics_service, alert_rule_service, alert_service, routing_service = _build()

        warning_route = ExecutionObservabilityAlertRoute(severity="WARNING", destination="slack:#alerts")
        error_route = ExecutionObservabilityAlertRoute(severity="ERROR", destination="pagerduty:oncall")
        routing_service.register(warning_route)
        routing_service.register(error_route)

        warning_alert = _trigger_alert(
            metrics_service, alert_rule_service, alert_service, "WARNING", metric="latency_ms"
        )
        error_alert = _trigger_alert(
            metrics_service, alert_rule_service, alert_service, "ERROR", metric="memory_mb"
        )

        assert routing_service.resolve(warning_alert.alert_id) == warning_route
        assert routing_service.resolve(error_alert.alert_id) == error_route

    def test_route_precedence(self):
        metrics_service, alert_rule_service, alert_service, routing_service = _build()

        general_route = ExecutionObservabilityAlertRoute(severity="ANY", destination="slack:#general")
        specific_route = ExecutionObservabilityAlertRoute(severity="WARNING", destination="slack:#alerts")
        routing_service.register(general_route)
        routing_service.register(specific_route)

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, "WARNING")

        assert routing_service.resolve(alert.alert_id) == specific_route
        assert routing_service.routes("WARNING") == (specific_route, general_route)

    def test_precedence_tiebreak_uses_most_recent(self):
        _, _, _, routing_service = _build()

        older = ExecutionObservabilityAlertRoute(
            severity="WARNING",
            destination="slack:#old",
            created_at=datetime.now(timezone.utc) - timedelta(seconds=10),
        )
        newer = ExecutionObservabilityAlertRoute(
            severity="WARNING",
            destination="slack:#new",
            created_at=datetime.now(timezone.utc),
        )
        routing_service.register(older)
        routing_service.register(newer)

        assert routing_service.routes("WARNING")[0] == newer

    def test_disabled_route_ignored(self):
        metrics_service, alert_rule_service, alert_service, routing_service = _build()

        route = ExecutionObservabilityAlertRoute(severity="WARNING", destination="slack:#alerts")
        routing_service.register(route)
        routing_service.disable(route.route_id)

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, "WARNING")

        assert routing_service.resolve(alert.alert_id) is None
        assert routing_service.routes("WARNING") == ()

    def test_disable_is_idempotent(self):
        _, _, _, routing_service = _build()

        route = ExecutionObservabilityAlertRoute(severity="WARNING", destination="slack:#alerts")
        routing_service.register(route)

        first = routing_service.disable(route.route_id)
        second = routing_service.disable(route.route_id)

        assert first == second

    def test_disable_unknown_route_rejection(self):
        _, _, _, routing_service = _build()

        with pytest.raises(Error):
            routing_service.disable("does-not-exist")

    def test_unrouted_alert(self):
        metrics_service, alert_rule_service, alert_service, routing_service = _build()

        alert = _trigger_alert(metrics_service, alert_rule_service, alert_service, "WARNING")

        assert routing_service.resolve(alert.alert_id) is None

    def test_multiple_destinations(self):
        metrics_service, alert_rule_service, alert_service, routing_service = _build()

        debug_route = ExecutionObservabilityAlertRoute(severity="DEBUG", destination="log:debug")
        warning_route = ExecutionObservabilityAlertRoute(severity="WARNING", destination="slack:#alerts")
        error_route = ExecutionObservabilityAlertRoute(severity="ERROR", destination="pagerduty:oncall")
        routing_service.register(debug_route)
        routing_service.register(warning_route)
        routing_service.register(error_route)

        warning_alert = _trigger_alert(
            metrics_service, alert_rule_service, alert_service, "WARNING", metric="latency_ms"
        )
        error_alert = _trigger_alert(
            metrics_service, alert_rule_service, alert_service, "ERROR", metric="memory_mb"
        )

        assert routing_service.resolve(warning_alert.alert_id).destination == "slack:#alerts"
        assert routing_service.resolve(error_alert.alert_id).destination == "pagerduty:oncall"

    def test_register_non_route_rejection(self):
        _, _, _, routing_service = _build()

        with pytest.raises(Error):
            routing_service.register({"not": "a route"})

    def test_resolve_unknown_alert_rejection(self):
        _, _, _, routing_service = _build()

        with pytest.raises(Error):
            routing_service.resolve("does-not-exist")
