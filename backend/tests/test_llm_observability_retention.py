from datetime import datetime, timedelta, timezone

import pytest

from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.observability_retention import (
    InvalidRetentionError,
    LLMObservabilityRetentionService,
    RetentionBoundaryError,
)
from backend.llm.request_errors import LLMRequestErrorService
from backend.llm.request_latency import LLMRequestLatencyService
from backend.llm.usage import LLMUsageRecord, LLMUsageService

NOW = datetime.now(timezone.utc)


def seed_usage(usage_service, usage_id, request_id, tokens, recorded_at, provider="openai", model="gpt-4o"):
    """Directly seeds a real LLMUsageService's storage with a controlled
    timestamp -- record() always stamps datetime.now(), so this is the only
    way to exercise purge_before() against genuinely old data."""
    record = LLMUsageRecord(
        usage_id=usage_id,
        request_id=request_id,
        provider=provider,
        model=model,
        input_tokens=tokens,
        output_tokens=0,
        total_tokens=tokens,
        recorded_at=recorded_at,
    )
    usage_service._records.append(record)
    usage_service._by_request.setdefault(request_id, []).append(record)
    return record


def build_env(retention_days=30):
    usage_service = LLMUsageService()
    cost_service = LLMCostService(usage_service)
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.0)
    )
    latency_service = LLMRequestLatencyService()
    error_service = LLMRequestErrorService()
    retention_service = LLMObservabilityRetentionService(
        usage_service,
        cost_service,
        latency_service,
        error_service,
        default_retention=timedelta(days=retention_days),
    )
    return usage_service, cost_service, latency_service, error_service, retention_service


def test_retention_boundary():
    _, _, _, _, retention_service = build_env(retention_days=30)

    default = retention_service.retention("req-1")
    assert default["retention_period"] == timedelta(days=30)
    assert default["configured"] is False

    retention_service.configure("req-1", timedelta(days=7))
    configured = retention_service.retention("req-1")
    assert configured["retention_period"] == timedelta(days=7)
    assert configured["configured"] is True

    # An unrelated scope is unaffected by req-1's override.
    assert retention_service.retention("req-2")["configured"] is False

    with pytest.raises(InvalidRetentionError):
        retention_service.configure("req-1", timedelta(days=0))


def test_old_data_purge():
    usage_service, _, _, _, retention_service = build_env(retention_days=30)
    seed_usage(usage_service, "u1", "req-1", 100, NOW - timedelta(days=40))

    result = retention_service.purge_before("req-1", NOW - timedelta(days=35))

    assert result["removed"]["usage"] == 1
    assert usage_service.records("req-1") == ()


def test_recent_data_preservation():
    usage_service, _, _, _, retention_service = build_env(retention_days=30)
    recent = seed_usage(usage_service, "u1", "req-1", 100, NOW - timedelta(days=5))

    with pytest.raises(RetentionBoundaryError):
        retention_service.purge_before("req-1", NOW)

    # Nothing was removed by the refused call.
    assert usage_service.records("req-1") == (recent,)


def test_aggregate_preservation():
    usage_service, _, _, _, retention_service = build_env(retention_days=30)
    seed_usage(usage_service, "u1", "req-1", 100, NOW - timedelta(days=40), provider="openai", model="gpt-4o")
    seed_usage(usage_service, "u2", "req-1", 50, NOW - timedelta(days=40), provider="gemini", model="gemini-1.5-pro")

    result = retention_service.purge_before("req-1", NOW - timedelta(days=35))

    by_provider = result["aggregate"]["usage"]["by_provider"]
    assert by_provider["openai"]["total_tokens"] == 100
    assert by_provider["gemini"]["total_tokens"] == 50
    by_model = result["aggregate"]["usage"]["by_model"]
    assert by_model["gpt-4o"]["total_tokens"] == 100
    assert by_model["gemini-1.5-pro"]["total_tokens"] == 50

    # The raw records are gone -- only the aggregate remembers the breakdown.
    assert usage_service.records("req-1") == ()


def test_scope_isolation():
    usage_service, _, _, _, retention_service = build_env(retention_days=30)
    seed_usage(usage_service, "u1", "scope-a", 100, NOW - timedelta(days=40))
    seed_usage(usage_service, "u2", "scope-b", 200, NOW - timedelta(days=40))

    retention_service.purge_before("scope-a", NOW - timedelta(days=35))

    assert usage_service.records("scope-a") == ()
    assert len(usage_service.records("scope-b")) == 1


def test_repeated_purge():
    usage_service, _, _, _, retention_service = build_env(retention_days=30)
    seed_usage(usage_service, "u1", "req-1", 100, NOW - timedelta(days=40))

    first = retention_service.purge_before("req-1", NOW - timedelta(days=35))
    assert first["removed"]["usage"] == 1

    second = retention_service.purge_before("req-1", NOW - timedelta(days=35))
    assert second["removed"]["usage"] == 0
    assert second["removed"]["latency"] == 0
    assert second["removed"]["error"] == 0


def test_empty_dataset():
    _, _, _, _, retention_service = build_env(retention_days=30)

    aggregate = retention_service.aggregate_before("req-1", NOW - timedelta(days=35))
    assert aggregate["usage"]["totals"]["count"] == 0
    assert aggregate["usage"]["by_provider"] == {}
    assert aggregate["cost"]["totals"]["count"] == 0

    result = retention_service.purge_before("req-1", NOW - timedelta(days=35))
    assert result["removed"] == {"usage": 0, "latency": 0, "error": 0}
