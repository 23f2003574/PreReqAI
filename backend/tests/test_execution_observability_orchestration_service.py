from datetime import (
    datetime,
    timedelta,
    timezone,
)

from backend.session import (
    ExecutionAlertAnalytics,
    ExecutionAlertAnalyticsService,
    ExecutionAlertCorrelationService,
    ExecutionAlertDeduplicationService,
    ExecutionAlertEscalationService,
    ExecutionAlertRoutingService,
    ExecutionAlertRuleService,
    ExecutionAlertService,
    ExecutionAlertSuppressionService,
    ExecutionEventService,
    ExecutionMetricsService,
    ExecutionObservabilityAlertRule,
    ExecutionObservabilityDecision,
    ExecutionObservabilityOrchestrationService,
    ExecutionTraceService,
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
    event_service = ExecutionEventService(runtime_service)
    trace_service = ExecutionTraceService(runtime_service)
    alert_rule_service = ExecutionAlertRuleService(metrics_service)
    alert_service = ExecutionAlertService(alert_rule_service, metrics_service)
    escalation_service = ExecutionAlertEscalationService(alert_service)
    suppression_service = ExecutionAlertSuppressionService()
    routing_service = ExecutionAlertRoutingService(alert_service)
    deduplication_service = ExecutionAlertDeduplicationService()
    correlation_service = ExecutionAlertCorrelationService(alert_service)
    analytics_service = ExecutionAlertAnalyticsService(alert_service, deduplication_service)

    orchestration_service = ExecutionObservabilityOrchestrationService(
        metrics_service,
        event_service,
        trace_service,
        alert_rule_service,
        alert_service,
        escalation_service,
        suppression_service,
        routing_service,
        deduplication_service,
        correlation_service,
        analytics_service,
    )

    return {
        "metrics": metrics_service,
        "events": event_service,
        "traces": trace_service,
        "rules": alert_rule_service,
        "alerts": alert_service,
        "escalation": escalation_service,
        "suppression": suppression_service,
        "routing": routing_service,
        "dedup": deduplication_service,
        "correlation": correlation_service,
        "analytics": analytics_service,
        "orchestration": orchestration_service,
    }


def _register_rule(services, metric="latency_ms", severity="WARNING", threshold=100):
    rule = ExecutionObservabilityAlertRule(
        name=f"{metric} rule", metric=metric, operator="GT", threshold=threshold, severity=severity
    )
    services["rules"].register(rule)

    return rule


class TestExecutionObservabilityOrchestrationService:
    def test_complete_collection(self):
        services = _build()

        services["metrics"].record("runtime-1", "latency_ms", 150, "ms")
        services["events"].record("runtime-1", "STARTED", "INFO", None)
        trace = services["traces"].start("runtime-1", "ingest_document")

        collected = services["orchestration"].collect("runtime-1")

        assert len(collected["metrics"]) == 1
        assert collected["metrics"][0].name == "latency_ms"
        assert len(collected["events"]) == 1
        assert collected["events"][0].event_type == "STARTED"
        assert collected["traces"] == (trace,)

    def test_alert_generation(self):
        services = _build()

        rule = _register_rule(services)
        services["metrics"].record("runtime-1", "latency_ms", 150, "ms")

        result = services["orchestration"].evaluate("runtime-1")

        assert len(result["new_alerts"]) == 1
        assert result["new_alerts"][0].rule_id == rule.rule_id
        assert result["duplicate_alerts"] == ()
        assert result["suppressed_rule_ids"] == ()

        active = services["orchestration"].alerts("runtime-1")
        assert active == result["new_alerts"]

    def test_suppression_handling(self):
        services = _build()

        rule = _register_rule(services)
        services["metrics"].record("runtime-1", "latency_ms", 150, "ms")
        services["suppression"].suppress(
            rule.rule_id,
            "runtime-1",
            "known noisy alert",
            datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        result = services["orchestration"].evaluate("runtime-1")

        assert result["new_alerts"] == ()
        assert result["suppressed_rule_ids"] == (rule.rule_id,)
        assert services["orchestration"].alerts("runtime-1") == ()

    def test_deduplication(self):
        services = _build()

        _register_rule(services)
        services["metrics"].record("runtime-1", "latency_ms", 150, "ms")

        first_result = services["orchestration"].evaluate("runtime-1")
        assert len(first_result["new_alerts"]) == 1
        assert first_result["duplicate_alerts"] == ()

        second_result = services["orchestration"].evaluate("runtime-1")
        assert second_result["new_alerts"] == ()
        assert len(second_result["duplicate_alerts"]) == 1

    def test_correlation(self):
        services = _build()

        _register_rule(services)
        services["metrics"].record("runtime-1", "latency_ms", 150, "ms")
        first_result = services["orchestration"].evaluate("runtime-1")
        first_alert = first_result["new_alerts"][0]

        services["metrics"].record("runtime-2", "latency_ms", 150, "ms")
        second_result = services["orchestration"].evaluate("runtime-2")
        second_alert = second_result["new_alerts"][0]

        assert len(second_result["correlations"]) == 1

        correlation = second_result["correlations"][0]
        assert set(correlation.alert_ids) == {first_alert.alert_id, second_alert.alert_id}
        assert set(correlation.runtime_ids) == {"runtime-1", "runtime-2"}

    def test_analytics_inclusion(self):
        services = _build()

        _register_rule(services)
        services["metrics"].record("runtime-1", "latency_ms", 150, "ms")
        services["orchestration"].evaluate("runtime-1")

        summary = services["orchestration"].summary("runtime-1")

        assert isinstance(summary["analytics"], ExecutionAlertAnalytics)
        assert summary["analytics"].total_alerts == 1
        assert summary["analytics"].open_alerts == 1

        decision = services["orchestration"].decision("runtime-1")
        assert isinstance(decision, ExecutionObservabilityDecision)
        assert decision.health_summary["analytics"].total_alerts == 1

    def test_deterministic_decision(self):
        services = _build()

        _register_rule(services, severity="ERROR")
        services["metrics"].record("runtime-1", "latency_ms", 150, "ms")
        services["orchestration"].evaluate("runtime-1")

        first = services["orchestration"].decision("runtime-1")
        second = services["orchestration"].decision("runtime-1")

        assert first.status == second.status == "CRITICAL"
        assert first.alert_count == second.alert_count == 1

        first_analytics = first.health_summary["analytics"]
        second_analytics = second.health_summary["analytics"]
        assert first_analytics.total_alerts == second_analytics.total_alerts
        assert first_analytics.open_alerts == second_analytics.open_alerts
        assert first_analytics.critical_count == second_analytics.critical_count
        assert first_analytics.recurrence_rate == second_analytics.recurrence_rate
        assert first.health_summary["escalation_levels"] == second.health_summary["escalation_levels"]

    def test_decision_healthy_when_no_open_alerts(self):
        services = _build()

        decision = services["orchestration"].decision("runtime-1")

        assert decision.status == "HEALTHY"
        assert decision.alert_count == 0

    def test_decision_warning_for_non_critical_open_alert(self):
        services = _build()

        _register_rule(services, severity="WARNING")
        services["metrics"].record("runtime-1", "latency_ms", 150, "ms")
        services["orchestration"].evaluate("runtime-1")

        decision = services["orchestration"].decision("runtime-1")

        assert decision.status == "WARNING"
        assert decision.alert_count == 1
