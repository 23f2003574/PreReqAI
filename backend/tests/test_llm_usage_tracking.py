import dataclasses

import pytest

from backend.llm import LLMResponse
from backend.llm.usage import InvalidUsageError, LLMUsageService, UnknownRequestError


def make_response(
    model="gpt-4o", prompt_tokens=10, completion_tokens=5, usage_override=None
):
    usage = usage_override
    if usage is None:
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
    return LLMResponse(content="hello", model=model, usage=usage, finish_reason="stop")


def test_record_usage():
    service = LLMUsageService()
    response = make_response()

    record = service.record(response, request_id="req-1", provider="openai")

    assert record.usage_id
    assert record.request_id == "req-1"
    assert record.provider == "openai"
    assert record.model == "gpt-4o"
    assert record.input_tokens == 10
    assert record.output_tokens == 5
    assert record.total_tokens == 15
    assert record.recorded_at is not None

    # total_tokens is always recomputed from input+output, not trusted from the raw payload
    mismatched = service.record(
        make_response(
            usage_override={
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 999,
            }
        ),
        request_id="req-1",
        provider="openai",
    )
    assert mismatched.total_tokens == 15

    # tolerant of differently-named provider usage keys
    aliased = service.record(
        make_response(usage_override={"input_tokens": 3, "output_tokens": 2}),
        request_id="req-1",
        provider="gemini",
    )
    assert aliased.total_tokens == 5


def test_total_calculation():
    service = LLMUsageService()
    service.record(make_response(prompt_tokens=10, completion_tokens=5), "req-2", "openai")
    service.record(make_response(prompt_tokens=20, completion_tokens=10), "req-2", "openai")
    service.record(make_response(prompt_tokens=1, completion_tokens=1), "req-3", "gemini")

    assert service.total("req-2") == 45
    assert service.total("req-3") == 2
    assert service.total() == 47
    assert service.total("unknown-request") == 0


def test_request_lookup():
    service = LLMUsageService()
    service.record(make_response(), "req-4", "openai")
    service.record(make_response(prompt_tokens=1, completion_tokens=1), "req-4", "openai")

    records = service.get("req-4")
    assert len(records) == 2
    assert all(record.request_id == "req-4" for record in records)

    with pytest.raises(UnknownRequestError):
        service.get("does-not-exist")


def test_model_aggregation():
    service = LLMUsageService()
    service.record(
        make_response(model="gpt-4o", prompt_tokens=10, completion_tokens=5), "req-5", "openai"
    )
    service.record(
        make_response(model="gpt-4o-mini", prompt_tokens=4, completion_tokens=2),
        "req-5",
        "openai",
    )
    service.record(
        make_response(model="gpt-4o", prompt_tokens=1, completion_tokens=1), "req-6", "openai"
    )

    assert service.by_model("req-5") == {"gpt-4o": 15, "gpt-4o-mini": 6}

    global_by_model = service.by_model()
    assert global_by_model["gpt-4o"] == 17
    assert global_by_model["gpt-4o-mini"] == 6


def test_invalid_counts():
    service = LLMUsageService()

    with pytest.raises(InvalidUsageError):
        service.record(
            make_response(
                usage_override={
                    "prompt_tokens": -1,
                    "completion_tokens": 5,
                    "total_tokens": 4,
                }
            ),
            "req-7",
            "openai",
        )

    with pytest.raises(InvalidUsageError):
        service.record(
            make_response(
                usage_override={
                    "prompt_tokens": 5,
                    "completion_tokens": -2,
                    "total_tokens": 3,
                }
            ),
            "req-7",
            "openai",
        )

    with pytest.raises(InvalidUsageError):
        service.record(
            make_response(usage_override={"total_tokens": 5}),
            "req-7",
            "openai",
        )

    with pytest.raises(InvalidUsageError):
        service.record(make_response(), request_id="", provider="openai")


def test_immutable_records():
    service = LLMUsageService()
    record = service.record(make_response(), "req-8", "openai")

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.input_tokens = 999

    returned = service.get("req-8")
    assert isinstance(returned, tuple)

    service.record(make_response(), "req-8", "openai")
    assert len(returned) == 1  # earlier lookup unaffected by a later record() call
    assert len(service.get("req-8")) == 2
