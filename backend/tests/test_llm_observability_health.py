from datetime import datetime, timedelta, timezone

from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.cost_analytics import LLMCostAnalyticsService
from backend.llm.observability_dashboard import LLMObservabilityDashboardService
from backend.llm.observability_health import (
    CRITICAL,
    DEGRADED,
    HEALTHY,
    UNKNOWN,
    LLMObservabilityHealthService,
)
from backend.llm.request_latency import LLMRequestLatency
from backend.llm.usage import LLMUsageRecord
from backend.llm.usage_aggregation import LLMUsageAggregationService
from backend.llm.usage_anomalies import LLMUsageAnomalyService

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


def build_env(usage_records, latency_records, **health_kwargs):
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
    health_service = LLMObservabilityHealthService(dashboard_service, **health_kwargs)
    return health_service


def steady_usage(tokens_per_day=100):
    return [
        make_usage("u1", "req-1", tokens_per_day, DAY1 + timedelta(hours=1)),
        make_usage("u2", "req-1", tokens_per_day, DAY2 + timedelta(hours=1)),
        make_usage("u3", "req-1", tokens_per_day, DAY3 + timedelta(hours=1)),
    ]


def latencies_with_failures(total=10, failures=0):
    records = []
    for i in range(total):
        status = "failed" if i < failures else "succeeded"
        records.append(make_latency("req-1", status, 1.0, DAY3 + timedelta(hours=1, minutes=i)))
    return records


def test_healthy_system():
    health_service = build_env(steady_usage(), latencies_with_failures(total=10, failures=0))

    result = health_service.assess("req-1", PERIOD)

    assert result["status"] == HEALTHY
    assert all(f["severity"] == HEALTHY for f in result["findings"])


def test_degraded_metrics():
    # 2/10 = 0.2 failure rate: above the default 0.1 degraded threshold,
    # below the default 0.3 critical threshold.
    health_service = build_env(steady_usage(), latencies_with_failures(total=10, failures=2))

    assert health_service.status("req-1", PERIOD) == DEGRADED
    error_finding = next(f for f in health_service.findings("req-1", PERIOD) if f["check"] == "error_rate")
    assert error_finding["severity"] == DEGRADED


def test_critical_anomaly():
    spiking_usage = [
        make_usage("u1", "req-1", 100, DAY1 + timedelta(hours=1)),
        make_usage("u2", "req-1", 100, DAY2 + timedelta(hours=1)),
        make_usage("u3", "req-1", 500, DAY3 + timedelta(hours=1)),
    ]
    health_service = build_env(spiking_usage, latencies_with_failures(total=10, failures=0))

    result = health_service.assess("req-1", PERIOD)

    assert result["status"] == CRITICAL
    assert any(f["check"] == "anomaly:TOKENS" and f["severity"] == CRITICAL for f in result["findings"])


def test_insufficient_data():
    health_service = build_env([], [])

    result = health_service.assess("req-1", PERIOD)

    assert result["status"] == UNKNOWN
    assert result["findings"] == [
        {
            "check": "data_sufficiency",
            "severity": UNKNOWN,
            "detail": "no completed requests recorded in this period",
        }
    ]


def test_threshold_handling():
    # A 0.2 failure rate is DEGRADED under defaults, but CRITICAL under a
    # stricter, explicitly configured critical threshold.
    lenient = build_env(steady_usage(), latencies_with_failures(total=10, failures=2))
    strict = build_env(
        steady_usage(),
        latencies_with_failures(total=10, failures=2),
        critical_failure_rate=0.15,
    )

    assert lenient.status("req-1", PERIOD) == DEGRADED
    assert strict.status("req-1", PERIOD) == CRITICAL


def test_multiple_findings():
    spiking_usage = [
        make_usage("u1", "req-1", 100, DAY1 + timedelta(hours=1)),
        make_usage("u2", "req-1", 100, DAY2 + timedelta(hours=1)),
        make_usage("u3", "req-1", 500, DAY3 + timedelta(hours=1)),
    ]
    health_service = build_env(spiking_usage, latencies_with_failures(total=10, failures=2))

    result = health_service.assess("req-1", PERIOD)

    checks = {f["check"] for f in result["findings"]}
    assert "error_rate" in checks
    assert "anomaly:TOKENS" in checks
    assert "data_sufficiency" in checks
    assert result["status"] == CRITICAL  # the anomaly's CRITICAL outranks the DEGRADED error_rate


def test_deterministic_status():
    health_service = build_env(steady_usage(), latencies_with_failures(total=10, failures=0))

    first = health_service.assess("req-1", PERIOD)
    second = health_service.assess("req-1", PERIOD)

    assert first["status"] == second["status"]
    assert first["findings"] == second["findings"]
