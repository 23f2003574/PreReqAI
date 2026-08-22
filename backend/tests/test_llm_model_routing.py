import pytest

from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.routing import (
    LLMModelRoutingService,
    LLMRouteRequest,
    NoEligibleModelError,
    ProviderCapabilityProfile,
)


def build_routing_service():
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY")
    )
    config_service.register(
        LLMProviderConfig(
            provider="gemini", model="gemini-1.5-pro", api_key_ref="GEMINI_KEY"
        )
    )
    config_service.register(
        LLMProviderConfig(provider="local", model="llama3", api_key_ref="LOCAL_KEY")
    )

    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai",
        ProviderCapabilityProfile(
            capabilities={"chat", "vision", "function_calling"}, cost=0.03, latency=1.2
        ),
    )
    routing_service.register_capability_profile(
        "gemini",
        ProviderCapabilityProfile(capabilities={"chat", "vision"}, cost=0.02, latency=0.9),
    )
    routing_service.register_capability_profile(
        "local",
        ProviderCapabilityProfile(capabilities={"chat"}, cost=0.0, latency=2.5),
    )

    return config_service, routing_service


def test_capability_filtering():
    _, routing_service = build_routing_service()

    function_calling_routes = routing_service.rank(
        LLMRouteRequest(task="summarize", required_capabilities=["function_calling"])
    )
    assert [route.provider for route in function_calling_routes] == ["openai"]

    vision_routes = routing_service.rank(
        LLMRouteRequest(task="summarize", required_capabilities=["vision"])
    )
    assert {route.provider for route in vision_routes} == {"openai", "gemini"}

    chat_routes = routing_service.rank(
        LLMRouteRequest(task="summarize", required_capabilities=["chat"])
    )
    assert {route.provider for route in chat_routes} == {"openai", "gemini", "local"}


def test_provider_preference():
    _, routing_service = build_routing_service()

    route = routing_service.resolve(
        LLMRouteRequest(
            task="summarize",
            preferred_provider="gemini",
            required_capabilities=["chat"],
        )
    )
    assert route.provider == "gemini"
    assert route.model == "gemini-1.5-pro"
    assert "preferred_provider" in route.reason

    with pytest.raises(NoEligibleModelError):
        routing_service.resolve(
            LLMRouteRequest(
                task="summarize",
                preferred_provider="local",
                required_capabilities=["function_calling"],
            )
        )


def test_cost_latency_constraints():
    _, routing_service = build_routing_service()

    cheap_routes = routing_service.rank(
        LLMRouteRequest(task="summarize", required_capabilities=["chat"], max_cost=0.01)
    )
    assert [route.provider for route in cheap_routes] == ["local"]

    fast_routes = routing_service.rank(
        LLMRouteRequest(
            task="summarize", required_capabilities=["chat"], max_latency=1.0
        )
    )
    assert [route.provider for route in fast_routes] == ["gemini"]

    with pytest.raises(ValueError):
        routing_service.resolve(
            LLMRouteRequest(
                task="summarize", required_capabilities=["chat"], max_cost=-1.0
            )
        )


def test_deterministic_ranking():
    _, routing_service = build_routing_service()
    request = LLMRouteRequest(task="summarize", required_capabilities=["chat"])

    first = routing_service.rank(request)
    second = routing_service.rank(request)

    assert first == second
    assert [route.provider for route in first] == ["openai", "gemini", "local"]


def test_disabled_provider():
    config_service, routing_service = build_routing_service()
    config_service.disable("local")

    routes = routing_service.rank(
        LLMRouteRequest(task="summarize", required_capabilities=["chat"])
    )
    assert "local" not in {route.provider for route in routes}
    assert "local" not in routing_service.available()

    with pytest.raises(NoEligibleModelError):
        routing_service.resolve(
            LLMRouteRequest(
                task="summarize",
                preferred_provider="local",
                required_capabilities=["chat"],
            )
        )


def test_no_eligible_model():
    _, routing_service = build_routing_service()

    routes = routing_service.rank(
        LLMRouteRequest(task="transcribe", required_capabilities=["audio_transcription"])
    )
    assert routes == []

    with pytest.raises(NoEligibleModelError):
        routing_service.resolve(
            LLMRouteRequest(
                task="transcribe", required_capabilities=["audio_transcription"]
            )
        )
