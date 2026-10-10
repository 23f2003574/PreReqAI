from datetime import datetime, timezone

import pytest

from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.cost_analytics import LLMCostAnalyticsService
from backend.llm.usage import LLMUsageRecord
from backend.llm.usage_aggregation import LLMUsageAggregationService
from backend.llm.request_latency import LLMRequestLatency
from backend.llm.usage_anomalies import (
    COST,
    CRITICAL,
    ERROR_RATE,
    LATENCY,
    MODERATE,
    NORMAL,
    TOKENS,
    UNKNOWN,
    LLMUsageAnomalyService,
)

DAY1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
DAY2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
DAY3 = datetime(2026, 1, 3, tzinfo=timezone.utc)
DAY4 = datetime(2026, 1, 4, tzinfo=timezone.utc)
PERIOD = (DAY3, DAY4)  # history windows (history_periods=2): (DAY2,DAY3), (DAY1,DAY2)


class FakeUsageService:
    """Minimal stand-in matching LLMUsageService.records(scope_id), used to
    control historical timestamps precisely -- record() always stamps now()."""

    def __init__(self, records):
        self._records = records

    def records(self, scope_id=None):
        if scope_id is None:
            return tuple(self._records)
        return tuple(r for r in self._records if r.request_id == scope_id)


class FakeLatencyService:
    """Same idea as FakeUsageService, for LLMRequestLatencyService.records()."""

    def __init__(self, records):
        self._records = records

    def records(self, scope=None):
        if scope is None:
            return tuple(self._records)
        return tuple(r for r in self._records if r.request_id == scope)


def make_usage_record(usage_id, request_id, tokens, recorded_at, provider="openai", model="gpt-4o"):
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


def build_token_env(day1_tokens, day2_tokens, day3_tokens):
    records = [
        make_usage_record("u1", "req-1", day1_tokens, DAY1 + (DAY2 - DAY1) / 2),
        make_usage_record("u2", "req-2", day2_tokens, DAY2 + (DAY3 - DAY2) / 2),
        make_usage_record("u3", "req-3", day3_tokens, DAY3 + (DAY4 - DAY3) / 2),
    ]
    usage_service = FakeUsageService(records)
    usage_analytics = LLMUsageAggregationService(usage_service)
    cost_service = LLMCostService(usage_service)
    cost_analytics = LLMCostAnalyticsService(usage_service, cost_service)
    anomaly_service = LLMUsageAnomalyService(
        usage_analytics, cost_analytics, FakeLatencyService([]), history_periods=2
    )
    return anomaly_service


def find(results, metric):
    return next(r for r in results if r.metric == metric)


def test_normal_usage():
    service = build_token_env(day1_tokens=100, day2_tokens=100, day3_tokens=105)

    results = service.detect(None, PERIOD)

    tokens = find(results, TOKENS)
    assert tokens.baseline == 100.0
    assert tokens.observed == 105.0
    assert tokens.severity == NORMAL


def test_token_spike():
    service = build_token_env(day1_tokens=100, day2_tokens=100, day3_tokens=500)

    tokens = find(service.detect(None, PERIOD), TOKENS)

    assert tokens.baseline == 100.0
    assert tokens.observed == 500.0
    assert tokens.deviation == 4.0
    assert tokens.severity == CRITICAL


def test_cost_spike():
    records = [
        make_usage_record("u1", "req-1", 100, DAY1 + (DAY2 - DAY1) / 2),
        make_usage_record("u2", "req-2", 100, DAY2 + (DAY3 - DAY2) / 2),
        make_usage_record("u3", "req-3", 500, DAY3 + (DAY4 - DAY3) / 2),
    ]
    usage_service = FakeUsageService(records)
    usage_analytics = LLMUsageAggregationService(usage_service)
    cost_service = LLMCostService(usage_service)
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.0)
    )
    cost_analytics = LLMCostAnalyticsService(usage_service, cost_service)
    service = LLMUsageAnomalyService(
        usage_analytics, cost_analytics, FakeLatencyService([]), history_periods=2
    )

    cost = find(service.detect(None, PERIOD), COST)

    assert cost.baseline == 1.0
    assert cost.observed == 5.0
    assert cost.deviation == 4.0
    assert cost.severity == CRITICAL


def test_latency_spike():
    latencies = [
        make_latency("req-1", "succeeded", 1.0, DAY1 + (DAY2 - DAY1) / 2),
        make_latency("req-2", "succeeded", 1.0, DAY2 + (DAY3 - DAY2) / 2),
        make_latency("req-3", "succeeded", 5.0, DAY3 + (DAY4 - DAY3) / 2),
    ]
    empty_usage = FakeUsageService([])
    service = LLMUsageAnomalyService(
        LLMUsageAggregationService(empty_usage),
        LLMCostAnalyticsService(empty_usage, LLMCostService(empty_usage)),
        FakeLatencyService(latencies),
        history_periods=2,
    )

    latency = find(service.detect(None, PERIOD), LATENCY)

    assert latency.baseline == 1.0
    assert latency.observed == 5.0
    assert latency.deviation == 4.0
    assert latency.severity == CRITICAL


def test_error_spike():
    latencies = [
        make_latency("req-1", "succeeded", 1.0, DAY1 + (DAY2 - DAY1) / 2),
        make_latency("req-2", "succeeded", 1.0, DAY2 + (DAY3 - DAY2) / 2),
        make_latency("req-3", "failed", 1.0, DAY3 + (DAY4 - DAY3) / 2),
    ]
    empty_usage = FakeUsageService([])
    service = LLMUsageAnomalyService(
        LLMUsageAggregationService(empty_usage),
        LLMCostAnalyticsService(empty_usage, LLMCostService(empty_usage)),
        FakeLatencyService(latencies),
        history_periods=2,
    )

    error_rate = find(service.detect(None, PERIOD), ERROR_RATE)

    assert error_rate.baseline == 0.0
    assert error_rate.observed == 1.0
    assert error_rate.deviation == float("inf")
    assert error_rate.severity == CRITICAL


def test_insufficient_history():
    # Only DAY2-DAY3 has data; DAY1-DAY2 is empty, so history is incomplete.
    records = [
        make_usage_record("u2", "req-2", 100, DAY2 + (DAY3 - DAY2) / 2),
        make_usage_record("u3", "req-3", 500, DAY3 + (DAY4 - DAY3) / 2),
    ]
    usage_service = FakeUsageService(records)
    usage_analytics = LLMUsageAggregationService(usage_service)
    cost_service = LLMCostService(usage_service)
    cost_analytics = LLMCostAnalyticsService(usage_service, cost_service)
    service = LLMUsageAnomalyService(
        usage_analytics, cost_analytics, FakeLatencyService([]), history_periods=2
    )

    tokens = find(service.detect(None, PERIOD), TOKENS)

    assert tokens.severity == UNKNOWN
    assert tokens.baseline is None
    assert tokens.deviation is None
    # observed is still reported even without a baseline to compare against.
    assert tokens.observed == 500.0


def test_severity_classification():
    normal = find(
        build_token_env(day1_tokens=100, day2_tokens=100, day3_tokens=110).detect(None, PERIOD),
        TOKENS,
    )
    moderate = find(
        build_token_env(day1_tokens=100, day2_tokens=100, day3_tokens=170).detect(None, PERIOD),
        TOKENS,
    )
    critical = find(
        build_token_env(day1_tokens=100, day2_tokens=100, day3_tokens=400).detect(None, PERIOD),
        TOKENS,
    )

    assert normal.severity == NORMAL
    assert moderate.deviation == 0.7
    assert moderate.severity == MODERATE
    assert critical.deviation == 3.0
    assert critical.severity == CRITICAL


def test_scope_isolation():
    records = [
        make_usage_record("u1a", "scope-a", 100, DAY1 + (DAY2 - DAY1) / 2),
        make_usage_record("u2a", "scope-a", 100, DAY2 + (DAY3 - DAY2) / 2),
        make_usage_record("u3a", "scope-a", 500, DAY3 + (DAY4 - DAY3) / 2),
        make_usage_record("u1b", "scope-b", 50, DAY1 + (DAY2 - DAY1) / 2),
        make_usage_record("u2b", "scope-b", 50, DAY2 + (DAY3 - DAY2) / 2),
        make_usage_record("u3b", "scope-b", 55, DAY3 + (DAY4 - DAY3) / 2),
    ]
    usage_service = FakeUsageService(records)
    usage_analytics = LLMUsageAggregationService(usage_service)
    cost_service = LLMCostService(usage_service)
    cost_analytics = LLMCostAnalyticsService(usage_service, cost_service)
    service = LLMUsageAnomalyService(
        usage_analytics, cost_analytics, FakeLatencyService([]), history_periods=2
    )

    tokens_a = find(service.detect("scope-a", PERIOD), TOKENS)
    tokens_b = find(service.detect("scope-b", PERIOD), TOKENS)

    assert tokens_a.severity == CRITICAL
    assert tokens_b.severity == NORMAL
    assert service.critical("scope-a") and all(a.scope == "scope-a" for a in service.critical("scope-a"))
    assert service.critical("scope-b") == []
    assert [a.metric for a in service.by_metric("scope-a", TOKENS)] == [TOKENS]
