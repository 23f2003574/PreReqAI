from datetime import datetime, timedelta, timezone

import pytest

from backend.llm.models import LLMResponse
from backend.llm.usage import LLMUsageRecord, LLMUsageService
from backend.llm.usage_aggregation import LLMUsageAggregationService


def make_response(model, input_tokens, output_tokens):
    return LLMResponse(
        content="ok",
        model=model,
        usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
    )


def test_total_usage():
    usage_service = LLMUsageService()
    usage_service.record(make_response("gpt-4o", 10, 5), "req-1", "openai")
    usage_service.record(make_response("gpt-4o", 20, 8), "req-2", "openai")

    aggregation = LLMUsageAggregationService(usage_service)
    totals = aggregation.totals()

    assert totals == {"input_tokens": 30, "output_tokens": 13, "total_tokens": 43, "count": 2}


def test_provider_aggregation():
    usage_service = LLMUsageService()
    usage_service.record(make_response("gpt-4o", 10, 5), "req-1", "openai")
    usage_service.record(make_response("gemini-1.5-pro", 7, 3), "req-2", "gemini")
    usage_service.record(make_response("gpt-4o", 4, 2), "req-3", "openai")

    aggregation = LLMUsageAggregationService(usage_service)
    by_provider = aggregation.by_provider()

    assert by_provider["openai"] == {
        "input_tokens": 14,
        "output_tokens": 7,
        "total_tokens": 21,
        "count": 2,
    }
    assert by_provider["gemini"] == {
        "input_tokens": 7,
        "output_tokens": 3,
        "total_tokens": 10,
        "count": 1,
    }


def test_model_aggregation():
    usage_service = LLMUsageService()
    usage_service.record(make_response("gpt-4o", 10, 5), "req-1", "openai")
    usage_service.record(make_response("gpt-4o-mini", 6, 2), "req-2", "openai")
    usage_service.record(make_response("gpt-4o", 4, 2), "req-3", "openai")

    aggregation = LLMUsageAggregationService(usage_service)
    by_model = aggregation.by_model()

    assert by_model["gpt-4o"] == {
        "input_tokens": 14,
        "output_tokens": 7,
        "total_tokens": 21,
        "count": 2,
    }
    assert by_model["gpt-4o-mini"] == {
        "input_tokens": 6,
        "output_tokens": 2,
        "total_tokens": 8,
        "count": 1,
    }


class FakeUsageService:
    """A minimal stand-in exposing the exact records(scope_id) contract
    LLMUsageService already has, so period filtering can be tested against
    fixed, deterministic timestamps instead of the real clock."""

    def __init__(self, records):
        self._records = records

    def records(self, scope_id=None):
        if scope_id is None:
            return tuple(self._records)
        return tuple(record for record in self._records if record.request_id == scope_id)


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
    day1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    day2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    day3 = datetime(2026, 1, 3, tzinfo=timezone.utc)

    fake = FakeUsageService(
        [
            make_record("u1", "req-1", "openai", "gpt-4o", 10, 5, day1),
            make_record("u2", "req-2", "openai", "gpt-4o", 20, 8, day2),
            make_record("u3", "req-3", "openai", "gpt-4o", 40, 16, day3),
        ]
    )
    aggregation = LLMUsageAggregationService(fake)

    in_range = aggregation.by_period(None, day1, day2)
    assert in_range == {"input_tokens": 30, "output_tokens": 13, "total_tokens": 43, "count": 2}

    only_day3 = aggregation.by_period(None, day3, day3)
    assert only_day3["count"] == 1
    assert only_day3["total_tokens"] == 56

    none_matching = aggregation.by_period(None, day3 + timedelta(days=1), day3 + timedelta(days=2))
    assert none_matching == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "count": 0}

    with pytest.raises(ValueError):
        aggregation.by_period(None, day2, day1)


def test_empty_scope():
    usage_service = LLMUsageService()
    aggregation = LLMUsageAggregationService(usage_service)

    assert aggregation.totals() == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "count": 0,
    }
    assert aggregation.by_provider() == {}
    assert aggregation.by_model() == {}
    assert aggregation.aggregate() == {
        "totals": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "count": 0},
        "by_provider": {},
        "by_model": {},
    }

    # A scope no request was ever recorded under is equally empty, not an error.
    usage_service.record(make_response("gpt-4o", 5, 5), "req-1", "openai")
    assert aggregation.totals(scope="does-not-exist") == {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "count": 0,
    }


def test_input_output_totals_kept_separate():
    usage_service = LLMUsageService()
    usage_service.record(make_response("gpt-4o", 100, 1), "req-1", "openai")

    aggregation = LLMUsageAggregationService(usage_service)
    totals = aggregation.totals()

    assert totals["input_tokens"] == 100
    assert totals["output_tokens"] == 1
    assert totals["total_tokens"] == 101


def test_scope_isolation():
    usage_service = LLMUsageService()
    usage_service.record(make_response("gpt-4o", 10, 5), "req-1", "openai")
    usage_service.record(make_response("gemini-1.5-pro", 50, 20), "req-2", "gemini")

    aggregation = LLMUsageAggregationService(usage_service)

    assert aggregation.totals(scope="req-1") == {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "count": 1,
    }
    assert aggregation.totals(scope="req-2") == {
        "input_tokens": 50,
        "output_tokens": 20,
        "total_tokens": 70,
        "count": 1,
    }
    assert aggregation.by_provider(scope="req-1") == {
        "openai": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "count": 1}
    }
    # The unscoped view still sees both -- scoping narrows, it never leaks the other way.
    assert set(aggregation.by_provider()) == {"openai", "gemini"}
