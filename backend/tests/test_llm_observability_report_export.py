import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.cost_analytics import LLMCostAnalyticsService
from backend.llm.observability_dashboard import LLMObservabilityDashboardService, SecretInScopeError
from backend.llm.observability_reports import (
    MalformedReportError,
    LLMObservabilityReportService,
    UnsupportedFormatError,
)
from backend.llm.request_latency import LLMRequestLatency
from backend.llm.usage import LLMUsageRecord
from backend.llm.usage_aggregation import LLMUsageAggregationService
from backend.llm.usage_anomalies import LLMUsageAnomalyService

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


def build_env():
    usage_records = [make_usage("u1", "req-1", 100, DAY3 + timedelta(hours=1))]
    latency_records = [make_latency("req-1", "succeeded", 1.5, DAY3 + timedelta(hours=1))]

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
    report_service = LLMObservabilityReportService(dashboard_service)
    return dashboard_service, report_service


def test_report_generation():
    dashboard_service, report_service = build_env()

    report = report_service.generate("req-1", (DAY3, DAY4))

    assert set(report) == {
        "scope",
        "period",
        "generated_at",
        "usage",
        "cost",
        "latency",
        "error_rate",
        "provider_reliability",
        "anomalies",
    }
    assert report["scope"] == "req-1"
    assert report_service.validate(report) is True

    with pytest.raises(MalformedReportError):
        report_service.validate({"scope": "req-1"})


def test_metric_preservation():
    dashboard_service, report_service = build_env()

    summary = dashboard_service.summary("req-1", (DAY3, DAY4))
    report = report_service.generate("req-1", (DAY3, DAY4))

    assert report["usage"] == summary["usage"]
    assert report["cost"] == summary["cost"]
    assert report["latency"] == summary["latency"]
    assert report["error_rate"] == summary["error_rate"]
    assert report["provider_reliability"] == summary["provider_reliability"]
    assert len(report["anomalies"]) == len(summary["anomalies"])


def test_time_range_handling():
    _, report_service = build_env()

    report = report_service.generate("req-1", (DAY3, DAY4))

    assert report["period"]["start"] == DAY3.isoformat()
    assert report["period"]["end"] == DAY4.isoformat()


def test_serialization():
    _, report_service = build_env()
    report = report_service.generate("req-1", (DAY3, DAY4))

    exported = report_service.export(report, "json")
    parsed = json.loads(exported)

    assert parsed["scope"] == "req-1"
    assert parsed["usage"]["total_tokens"] == 100
    assert parsed["period"]["start"] == DAY3.isoformat()
    assert isinstance(parsed["anomalies"], list)


def test_deterministic_output():
    _, report_service = build_env()
    report = report_service.generate("req-1", (DAY3, DAY4))

    first = report_service.export(report, "json")
    second = report_service.export(report, "json")
    assert first == second

    # Regenerating from the same underlying data yields the same metrics,
    # even though generated_at legitimately differs between calls.
    other_report = report_service.generate("req-1", (DAY3, DAY4))
    assert other_report["usage"] == report["usage"]
    assert other_report["cost"] == report["cost"]
    assert other_report["latency"] == report["latency"]
    assert other_report["error_rate"] == report["error_rate"]


def test_unsupported_format():
    _, report_service = build_env()
    report = report_service.generate("req-1", (DAY3, DAY4))

    with pytest.raises(UnsupportedFormatError):
        report_service.export(report, "xml")

    with pytest.raises(UnsupportedFormatError):
        report_service.export(report, "yaml")


def test_secret_exclusion():
    _, report_service = build_env()

    with pytest.raises(SecretInScopeError):
        report_service.generate("sk-liveAbCdEfGhIjKlMnOpQrSt", (DAY3, DAY4))
