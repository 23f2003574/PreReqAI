from datetime import datetime, timedelta, timezone

import pytest

from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.cost_analytics import LLMCostAnalyticsService
from backend.llm.observability_dashboard import (
    LLMObservabilityDashboardService,
    SecretInScopeError,
)
from backend.llm.request_latency import LLMRequestLatency
from backend.llm.usage import LLMUsageRecord
from backend.llm.usage_aggregation import LLMUsageAggregationService
from backend.llm.usage_anomalies import CRITICAL, TOKENS, LLMUsageAnomalyService

DAY1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
DAY2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
DAY3 = datetime(2026, 1, 3, tzinfo=timezone.utc)
DAY4 = datetime(2026, 1, 4, tzinfo=timezone.utc)


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


def build_env(usage_records, latency_records, pricing=None):
    usage_service = FakeUsageService(usage_records)
    usage_analytics = LLMUsageAggregationService(usage_service)
    cost_service = LLMCostService(usage_service)
    if pricing:
        cost_service.register_pricing(pricing)
    cost_analytics = LLMCostAnalyticsService(usage_service, cost_service)
    latency_service = FakeLatencyService(latency_records)
    anomaly_service = LLMUsageAnomalyService(
        usage_analytics, cost_analytics, latency_service, history_periods=2
    )
    dashboard = LLMObservabilityDashboardService(
        usage_analytics, cost_analytics, latency_service, anomaly_service
    )
    return dashboard


def test_complete_summary():
    usage_records = [make_usage("u1", "req-1", 100, DAY3 + timedelta(hours=1))]
    latency_records = [
        make_latency("req-1", "succeeded", 1.0, DAY3 + timedelta(hours=1)),
        make_latency("req-2", "failed", 3.0, DAY3 + timedelta(hours=2)),
    ]
    dashboard = build_env(
        usage_records,
        latency_records,
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.0),
    )

    summary = dashboard.summary("req-1", (DAY3, DAY4))

    assert set(summary) == {
        "usage",
        "cost",
        "latency",
        "error_rate",
        "provider_reliability",
        "anomalies",
    }
    assert summary["usage"]["total_tokens"] == 100
    assert summary["cost"]["by_currency"] == {"USD": 1.0}
    assert summary["latency"]["count"] == 1
    assert summary["latency"]["average_duration"] == 1.0
    assert summary["error_rate"] == 0.0
    assert summary["provider_reliability"]["count"] == 1
    assert isinstance(summary["anomalies"], list)


def test_provider_breakdown():
    latency_records = [
        make_latency("req-1", "succeeded", 1.0, DAY3 + timedelta(hours=1), provider="openai"),
        make_latency("req-2", "failed", 2.0, DAY3 + timedelta(hours=2), provider="gemini"),
    ]
    dashboard = build_env([], latency_records)

    providers = dashboard.providers(None, (DAY3, DAY4))

    assert providers["by_provider"]["openai"]["success_rate"] == 1.0
    assert providers["by_provider"]["gemini"]["success_rate"] == 0.0
    assert providers["by_model"]["gpt-4o"]["count"] == 2


def test_timeseries_aggregation():
    usage_records = [
        make_usage("u1", "req-1", 100, DAY1 + timedelta(hours=1)),
        make_usage("u2", "req-1", 200, DAY3 + timedelta(hours=1)),
    ]
    dashboard = build_env(usage_records, [])

    series = dashboard.timeseries("req-1", TOKENS, (DAY1, DAY4))

    assert len(series) == 3
    assert series[0]["value"] == 100.0
    assert series[1]["value"] is None
    assert series[2]["value"] == 200.0


def test_anomaly_inclusion():
    usage_records = [
        make_usage("u1", "req-1", 100, DAY1 + timedelta(hours=1)),
        make_usage("u2", "req-1", 100, DAY2 + timedelta(hours=1)),
        make_usage("u3", "req-1", 500, DAY3 + timedelta(hours=1)),
    ]
    dashboard = build_env(usage_records, [])

    anomalies = dashboard.anomalies("req-1", (DAY3, DAY4))
    tokens_anomaly = next(a for a in anomalies if a.metric == TOKENS)

    assert tokens_anomaly.severity == CRITICAL
    summary = dashboard.summary("req-1", (DAY3, DAY4))
    assert any(a.metric == TOKENS and a.severity == CRITICAL for a in summary["anomalies"])


def test_empty_period():
    dashboard = build_env([], [])

    summary = dashboard.summary("req-1", (DAY1, DAY2))

    assert summary["usage"]["total_tokens"] == 0
    assert summary["cost"]["by_currency"] == {}
    assert summary["latency"] == {"count": 0, "average_duration": None}
    assert summary["error_rate"] is None
    assert summary["provider_reliability"]["count"] == 0

    series = dashboard.timeseries("req-1", TOKENS, (DAY1, DAY2))
    assert series == [{"start": DAY1, "end": DAY2, "value": None}]

    providers = dashboard.providers("req-1", (DAY1, DAY2))
    assert providers == {"by_provider": {}, "by_model": {}}


def test_scope_isolation():
    usage_records = [
        make_usage("u1", "req-a", 100, DAY3 + timedelta(hours=1)),
        make_usage("u2", "req-b", 999, DAY3 + timedelta(hours=1)),
    ]
    dashboard = build_env(usage_records, [])

    summary_a = dashboard.summary("req-a", (DAY3, DAY4))
    summary_b = dashboard.summary("req-b", (DAY3, DAY4))

    assert summary_a["usage"]["total_tokens"] == 100
    assert summary_b["usage"]["total_tokens"] == 999


def test_secret_exclusion():
    dashboard = build_env([], [])
    leaked_scope = "sk-liveAbCdEfGhIjKlMnOpQrSt"

    with pytest.raises(SecretInScopeError):
        dashboard.summary(leaked_scope, (DAY1, DAY2))

    with pytest.raises(SecretInScopeError):
        dashboard.timeseries(leaked_scope, TOKENS, (DAY1, DAY2))

    with pytest.raises(SecretInScopeError):
        dashboard.providers(leaked_scope, (DAY1, DAY2))

    with pytest.raises(SecretInScopeError):
        dashboard.anomalies(leaked_scope, (DAY1, DAY2))
