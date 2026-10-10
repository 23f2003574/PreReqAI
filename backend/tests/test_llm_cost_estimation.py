import pytest

from backend.llm import LLMResponse
from backend.llm.cost import (
    InvalidPricingError,
    LLMCostService,
    LLMModelPricing,
    PricingAlreadyRegisteredError,
    UnknownPricingError,
)
from backend.llm.usage import LLMUsageService


def make_response(model="gpt-4o", prompt_tokens=10, completion_tokens=5):
    return LLMResponse(
        content="hello",
        model=model,
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        finish_reason="stop",
    )


def build_services():
    usage_service = LLMUsageService()
    cost_service = LLMCostService(usage_service)
    return usage_service, cost_service


def test_pricing_registration():
    _, cost_service = build_services()

    pricing = cost_service.register_pricing(
        LLMModelPricing(
            provider="openai", model="gpt-4o", input_cost=0.000005, output_cost=0.000015
        )
    )
    assert cost_service.model_cost("openai", "gpt-4o") is pricing

    with pytest.raises(PricingAlreadyRegisteredError):
        cost_service.register_pricing(
            LLMModelPricing(
                provider="openai", model="gpt-4o", input_cost=0.00001, output_cost=0.00002
            )
        )

    with pytest.raises(InvalidPricingError):
        cost_service.register_pricing(
            LLMModelPricing(
                provider="openai", model="gpt-4o-mini", input_cost=-1, output_cost=0.0
            )
        )


def test_input_output_calculation():
    usage_service, cost_service = build_services()
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )
    usage_service.record(
        make_response(prompt_tokens=10, completion_tokens=5), "req-1", "openai"
    )

    estimate = cost_service.estimate("req-1")

    assert estimate.input_cost == pytest.approx(0.1)
    assert estimate.output_cost == pytest.approx(0.1)


def test_total_cost():
    usage_service, cost_service = build_services()
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )
    usage_service.record(
        make_response(prompt_tokens=10, completion_tokens=5), "req-2", "openai"
    )
    usage_service.record(
        make_response(prompt_tokens=20, completion_tokens=10), "req-2", "openai"
    )

    estimate = cost_service.estimate("req-2")

    assert estimate.total_cost == pytest.approx(estimate.input_cost + estimate.output_cost)
    assert estimate.total_cost == pytest.approx(0.01 * 30 + 0.02 * 15)
    assert estimate.currency == "USD"


def test_unknown_pricing():
    usage_service, cost_service = build_services()
    usage_service.record(make_response(), "req-3", "openai")

    with pytest.raises(UnknownPricingError):
        cost_service.estimate("req-3")

    with pytest.raises(UnknownPricingError):
        cost_service.model_cost("openai", "does-not-exist")


def test_model_isolation():
    usage_service, cost_service = build_services()
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )
    cost_service.register_pricing(
        LLMModelPricing(
            provider="openai", model="gpt-4o-mini", input_cost=0.001, output_cost=0.002
        )
    )

    usage_service.record(
        make_response(model="gpt-4o", prompt_tokens=10, completion_tokens=5), "req-4", "openai"
    )
    usage_service.record(
        make_response(model="gpt-4o-mini", prompt_tokens=10, completion_tokens=5),
        "req-5",
        "openai",
    )

    expensive = cost_service.estimate("req-4")
    cheap = cost_service.estimate("req-5")

    assert expensive.total_cost > cheap.total_cost
    assert (
        cost_service.model_cost("openai", "gpt-4o").input_cost
        != cost_service.model_cost("openai", "gpt-4o-mini").input_cost
    )


def test_deterministic_estimate():
    usage_service, cost_service = build_services()
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )
    usage_service.record(
        make_response(prompt_tokens=10, completion_tokens=5), "req-6", "openai"
    )

    before = usage_service.get("req-6")
    first = cost_service.estimate("req-6")
    second = cost_service.estimate("req-6")
    after = usage_service.get("req-6")

    assert first == second
    assert before == after
