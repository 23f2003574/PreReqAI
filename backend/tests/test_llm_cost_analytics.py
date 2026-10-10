from datetime import datetime, timedelta, timezone

import pytest

from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.cost_analytics import LLMCostAnalyticsService
from backend.llm.models import LLMResponse
from backend.llm.usage import LLMUsageRecord, LLMUsageService


def make_response(model, input_tokens, output_tokens):
    return LLMResponse(
        content="ok",
        model=model,
        usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
    )


def build_env():
    usage_service = LLMUsageService()
    cost_service = LLMCostService(usage_service)
    analytics = LLMCostAnalyticsService(usage_service, cost_service)
    return usage_service, cost_service, analytics


def test_total_cost():
    usage_service, cost_service, analytics = build_env()
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )
    usage_service.record(make_response("gpt-4o", 100, 50), "req-1", "openai")

    total = analytics.total()

    assert total["by_currency"] == {"USD": 2.0}
    assert total["count"] == 1
    assert total["unpriced_count"] == 0
    assert total["unpriced"] == []


def test_provider_aggregation():
    usage_service, cost_service, analytics = build_env()
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )
    cost_service.register_pricing(
        LLMModelPricing(provider="gemini", model="gemini-1.5-pro", input_cost=0.005, output_cost=0.01)
    )
    usage_service.record(make_response("gpt-4o", 100, 50), "req-1", "openai")
    usage_service.record(make_response("gemini-1.5-pro", 200, 100), "req-2", "gemini")

    by_provider = analytics.by_provider()

    assert by_provider["openai"]["by_currency"] == {"USD": 2.0}
    assert by_provider["gemini"]["by_currency"] == {"USD": 2.0}
    assert by_provider["openai"]["count"] == 1
    assert by_provider["gemini"]["count"] == 1


def test_model_aggregation():
    usage_service, cost_service, analytics = build_env()
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o-mini", input_cost=0.001, output_cost=0.002)
    )
    usage_service.record(make_response("gpt-4o", 100, 50), "req-1", "openai")
    usage_service.record(make_response("gpt-4o-mini", 100, 50), "req-2", "openai")

    by_model = analytics.by_model()

    assert by_model["gpt-4o"]["by_currency"] == {"USD": 2.0}
    assert by_model["gpt-4o-mini"]["by_currency"] == {"USD": 0.2}


class FakeUsageService:
    """Minimal stand-in matching LLMUsageService.records(scope_id), used only
    for deterministic timestamps -- record() always stamps datetime.now()."""

    def __init__(self, records):
        self._records = records

    def records(self, scope_id=None):
        if scope_id is None:
            return tuple(self._records)
        return tuple(r for r in self._records if r.request_id == scope_id)


def make_record(usage_id, request_id, provider, model, input_tokens, output_tokens, recorded_at):
    return LLMUsageRecord(
        usage_id=usage_id,
        request_id=request_id,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        recorded_at=recorded_at,
    )


def test_period_filtering():
    _, cost_service, _ = build_env()
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )

    day1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    day2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    day3 = datetime(2026, 1, 3, tzinfo=timezone.utc)

    fake_usage = FakeUsageService(
        [
            make_record("u1", "req-1", "openai", "gpt-4o", 100, 50, day1),
            make_record("u2", "req-2", "openai", "gpt-4o", 100, 50, day2),
            make_record("u3", "req-3", "openai", "gpt-4o", 100, 50, day3),
        ]
    )
    analytics = LLMCostAnalyticsService(fake_usage, cost_service)

    in_range = analytics.by_period(None, day1, day2)
    assert in_range["by_currency"] == {"USD": 4.0}
    assert in_range["count"] == 2

    none_matching = analytics.by_period(None, day3 + timedelta(days=1), day3 + timedelta(days=2))
    assert none_matching["by_currency"] == {}
    assert none_matching["count"] == 0

    with pytest.raises(ValueError):
        analytics.by_period(None, day2, day1)


def test_currency_handling():
    usage_service, cost_service, analytics = build_env()
    cost_service.register_pricing(
        LLMModelPricing(
            provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02, currency="USD"
        )
    )
    cost_service.register_pricing(
        LLMModelPricing(
            provider="local-eu", model="eu-model", input_cost=0.01, output_cost=0.02, currency="EUR"
        )
    )
    usage_service.record(make_response("gpt-4o", 100, 50), "req-1", "openai")
    usage_service.record(make_response("eu-model", 100, 50), "req-2", "local-eu")

    total = analytics.total()

    assert total["by_currency"] == {"USD": 2.0, "EUR": 2.0}


def test_unknown_pricing():
    usage_service, cost_service, analytics = build_env()
    # No pricing registered at all.
    usage_service.record(make_response("mystery-model", 100, 50), "req-1", "mystery-provider")

    total = analytics.total()

    assert total["by_currency"] == {}
    assert total["count"] == 0
    assert total["unpriced_count"] == 1
    assert total["unpriced"] == [("mystery-provider", "mystery-model")]


def test_empty_scope():
    usage_service, cost_service, analytics = build_env()
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )

    assert analytics.total() == {"by_currency": {}, "count": 0, "unpriced_count": 0, "unpriced": []}
    assert analytics.by_provider() == {}
    assert analytics.by_model() == {}

    usage_service.record(make_response("gpt-4o", 10, 5), "req-1", "openai")
    assert analytics.total(scope="does-not-exist") == {
        "by_currency": {},
        "count": 0,
        "unpriced_count": 0,
        "unpriced": [],
    }
