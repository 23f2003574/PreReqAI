from datetime import datetime, timedelta, timezone

from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.cost_analytics import LLMCostAnalyticsService
from backend.llm.observability_dashboard import LLMObservabilityDashboardService
from backend.llm.observability_health import CRITICAL, DEGRADED, HEALTHY, UNKNOWN, LLMObservabilityHealthService
from backend.llm.observability_orchestration import LLMObservabilityOrchestrationService
from backend.llm.observability_reports import LLMObservabilityReportService
from backend.llm.request_latency import LLMRequestLatency
from backend.llm.usage import LLMUsageRecord
from backend.llm.usage_aggregation import LLMUsageAggregationService
from backend.llm.usage_anomalies import TOKENS, LLMUsageAnomalyService
from backend.llm.usage_anomaly_alerts import LLMUsageAnomalyAlertService

DAY1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
DAY2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
DAY3 = datetime(2026, 1, 3, tzinfo=timezone.utc)
DAY4 = datetime(2026, 1, 4, tzinfo=timezone.utc)
PERIOD = (DAY3, DAY4)


class FakeUsageService:
    def __init__(self, records):
        self._records = records

    def records(self, scope_id=None):
        if scope_id is None:
            return tuple(self._records)
        return tuple(r for r in self._records if r.request_id == scope_id)


class FakeLatencyService:
    def __init__(self, records):
        self._records = records

    def records(self, scope=None):
        if scope is None:
            return tuple(self._records)
        return tuple(r for r in self._records if r.request_id == scope)


def make_usage(usage_id, request_id, tokens, recorded_at, provider="openai", model="gpt-4o"):
    return LLMUsageRecord(
        usage_id=usage_id,
        request_id=request_id,
        provider=provider,
        model=model,
        input_tokens=tokens,
        output_tokens=0,
        total_tokens=tokens,
        recorded_at=recorded_at,
    )


def make_latency(request_id, status, duration, recorded_at, provider="openai", model="gpt-4o"):
    return LLMRequestLatency(
        request_id=request_id,
        provider=provider,
        model=model,
        duration=duration,
        status=status,
        recorded_at=recorded_at,
    )


def build_env(usage_records, latency_records):
    usage_service = FakeUsageService(usage_records)
    usage_analytics = LLMUsageAggregationService(usage_service)
    cost_service = LLMCostService(usage_service)
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.0)
    )
    cost_analytics = LLMCostAnalyticsService(usage_service, cost_service)
    latency_service = FakeLatencyService(latency_records)
    anomaly_service = LLMUsageAnomalyService(
        usage_analytics, cost_analytics, latency_service, history_periods=2
    )
    dashboard_service = LLMObservabilityDashboardService(
        usage_analytics, cost_analytics, latency_service, anomaly_service
    )
    health_service = LLMObservabilityHealthService(dashboard_service)
    alert_service = LLMUsageAnomalyAlertService(anomaly_service)
    report_service = LLMObservabilityReportService(dashboard_service)
    orchestration = LLMObservabilityOrchestrationService(
        dashboard_service, health_service, alert_service, report_service
    )
    return orchestration, alert_service


def steady_usage(request_id="req-1", tokens_per_day=100):
    return [
        make_usage("u1", request_id, tokens_per_day, DAY1 + timedelta(hours=1)),
        make_usage("u2", request_id, tokens_per_day, DAY2 + timedelta(hours=1)),
        make_usage("u3", request_id, tokens_per_day, DAY3 + timedelta(hours=1)),
    ]


def steady_latencies(request_id="req-1", total=10, failures=0):
    return [
        make_latency(request_id, "failed" if i < failures else "succeeded", 1.0, DAY3 + timedelta(hours=1, minutes=i))
        for i in range(total)
    ]


def spiking_usage(request_id="req-1", spike_tokens=500):
    return [
        make_usage("u1", request_id, 100, DAY1 + timedelta(hours=1)),
        make_usage("u2", request_id, 100, DAY2 + timedelta(hours=1)),
        make_usage("u3", request_id, spike_tokens, DAY3 + timedelta(hours=1)),
    ]


def test_complete_observability_workflow():
    orchestration, _ = build_env(steady_usage(), steady_latencies())

    result = orchestration.analyze("req-1", PERIOD)

    assert set(result) == {"metrics", "cost", "reliability", "anomalies", "alerts", "health"}
    assert set(result["metrics"]) == {"usage", "latency", "error_rate"}
    assert result["metrics"]["usage"]["total_tokens"] == 100
    assert result["cost"]["by_currency"] == {"USD": 1.0}
    assert result["reliability"]["count"] == 10
    assert isinstance(result["anomalies"], list)
    assert isinstance(result["alerts"], list)
    assert result["health"]["status"] in {HEALTHY, DEGRADED, CRITICAL, UNKNOWN}


def test_healthy_result():
    orchestration, _ = build_env(steady_usage(), steady_latencies(failures=0))

    result = orchestration.analyze("req-1", PERIOD)

    assert result["health"]["status"] == HEALTHY
    assert result["alerts"] == []


def test_degraded_result():
    orchestration, alert_service = build_env(spiking_usage(spike_tokens=170), steady_latencies(failures=0))

    result = orchestration.analyze("req-1", PERIOD)

    assert result["health"]["status"] == DEGRADED
    # Both TOKENS and COST spike together (cost derives from token usage),
    # so both metrics get their own confirmed anomaly and alert.
    assert len(result["alerts"]) == 2
    assert all(alert.severity == "MODERATE" for alert in result["alerts"])
    assert alert_service.unresolved("req-1") == result["alerts"]


def test_critical_result():
    orchestration, alert_service = build_env(spiking_usage(spike_tokens=500), steady_latencies(failures=0))

    result = orchestration.analyze("req-1", PERIOD)

    assert result["health"]["status"] == CRITICAL
    assert len(result["alerts"]) == 2
    assert all(alert.severity == "CRITICAL" for alert in result["alerts"])
    assert any("TOKENS" in alert.message for alert in result["alerts"])


def test_missing_data_handling():
    orchestration, _ = build_env([], [])

    result = orchestration.analyze("req-1", PERIOD)

    assert result["health"]["status"] == UNKNOWN
    assert result["alerts"] == []
    assert result["reliability"]["count"] == 0


def test_alert_propagation():
    orchestration, alert_service = build_env(spiking_usage(spike_tokens=500), steady_latencies(failures=0))

    result = orchestration.analyze("req-1", PERIOD)
    propagated = result["alerts"][0]

    # The alert genuinely exists in Commit #8's own store, not just the
    # orchestration's return value.
    stored = alert_service.list("req-1")
    assert len(stored) == 2
    assert propagated.alert_id in {a.alert_id for a in stored}
    assert propagated.anomaly_id in {a.anomaly_id for a in stored}


def test_scope_isolation():
    usage_records = steady_usage("scope-a") + spiking_usage("scope-b", spike_tokens=500)
    latency_records = steady_latencies("scope-a") + steady_latencies("scope-b")
    orchestration, alert_service = build_env(usage_records, latency_records)

    result_a = orchestration.analyze("scope-a", PERIOD)
    result_b = orchestration.analyze("scope-b", PERIOD)

    assert result_a["health"]["status"] == HEALTHY
    assert result_a["alerts"] == []
    assert result_b["health"]["status"] == CRITICAL
    assert len(result_b["alerts"]) == 2
    assert alert_service.unresolved("scope-a") == []


def test_deterministic_output():
    orchestration, _ = build_env(steady_usage(), steady_latencies(failures=0))

    first = orchestration.analyze("req-1", PERIOD)
    second = orchestration.analyze("req-1", PERIOD)

    assert first["metrics"] == second["metrics"]
    assert first["cost"] == second["cost"]
    assert first["reliability"] == second["reliability"]
    assert first["health"]["status"] == second["health"]["status"]
    assert first["health"]["findings"] == second["health"]["findings"]
