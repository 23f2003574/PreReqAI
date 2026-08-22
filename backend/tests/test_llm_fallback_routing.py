import pytest

from backend.llm import LLMProvider, LLMRequest
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.fallback import LLMFallbackPolicy, LLMFallbackRoutingService
from backend.llm.retry import LLMRetryPolicy, LLMRetryService, RetryExhaustedError, TransientLLMError
from backend.llm.routing import LLMModelRoutingService, LLMRouteRequest, NoEligibleModelError, ProviderCapabilityProfile

MODELS = {"openai": "gpt-4o", "gemini": "gemini-1.5-pro", "local": "llama3"}


def build_routing(disabled=None, capability_overrides=None):
    disabled = disabled or set()
    config_service = LLMProviderConfigService()
    for provider, model in MODELS.items():
        config_service.register(
            LLMProviderConfig(
                provider=provider,
                model=model,
                api_key_ref=f"{provider.upper()}_KEY",
                enabled=provider not in disabled,
            )
        )

    routing_service = LLMModelRoutingService(config_service)
    profiles = {
        "openai": ProviderCapabilityProfile(capabilities={"chat", "vision"}, cost=0.03, latency=1.0),
        "gemini": ProviderCapabilityProfile(capabilities={"chat", "vision"}, cost=0.02, latency=0.8),
        "local": ProviderCapabilityProfile(capabilities={"chat"}, cost=0.0, latency=2.0),
    }
    if capability_overrides:
        profiles.update(capability_overrides)
    for provider, profile in profiles.items():
        routing_service.register_capability_profile(provider, profile)

    return config_service, routing_service


class AlwaysTransientProvider(LLMProvider):
    """A real Commit #1 LLMProvider that always raises a transient failure."""

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        raise TransientLLMError("simulated outage")

    def stream(self, request):
        raise NotImplementedError


def test_primary_selection():
    _, routing_service = build_routing()
    fallback_service = LLMFallbackRoutingService(routing_service)
    fallback_service.configure(
        LLMFallbackPolicy(
            policy_id="p1", primary_provider="openai", fallback_providers=("gemini", "local")
        )
    )

    request = LLMRouteRequest(task="chat", preferred_provider="openai", required_capabilities=["chat"])
    route = fallback_service.resolve(request, "req-1")

    assert route.provider == "openai"
    assert fallback_service.history("req-1") == [{"provider": "openai", "outcome": "selected"}]


def test_provider_failover():
    _, routing_service = build_routing()
    fallback_service = LLMFallbackRoutingService(routing_service)
    fallback_service.configure(
        LLMFallbackPolicy(
            policy_id="p2", primary_provider="openai", fallback_providers=("gemini", "local")
        )
    )

    route_request = LLMRouteRequest(
        task="chat", preferred_provider="openai", required_capabilities=["chat"]
    )
    primary_route = fallback_service.resolve(route_request, "req-2")
    assert primary_route.provider == "openai"

    # reuse Commit #10's retry service: exhaust the primary provider for real before failing over
    retry_service = LLMRetryService()
    retry_service.configure(
        "req-2", LLMRetryPolicy(policy_id="rp", max_attempts=2, backoff_seconds=0.001)
    )
    chat_request = LLMRequest(model=primary_route.model, messages=[{"role": "user", "content": "hi"}])

    with pytest.raises(RetryExhaustedError):
        retry_service.execute(chat_request, "req-2", AlwaysTransientProvider(), scope_id="req-2")

    fallback_route = fallback_service.fallback(
        route_request, "req-2", failed_provider=primary_route.provider
    )
    assert fallback_route.provider == "gemini"

    history = fallback_service.history("req-2")
    assert [h["provider"] for h in history] == ["openai", "openai", "gemini"]
    assert history[1]["outcome"] == "failed"
    assert history[2]["outcome"] == "selected"


def test_disabled_provider_skip():
    _, routing_service = build_routing(disabled={"gemini"})
    fallback_service = LLMFallbackRoutingService(routing_service)
    fallback_service.configure(
        LLMFallbackPolicy(
            policy_id="p3", primary_provider="openai", fallback_providers=("gemini", "local")
        )
    )

    request = LLMRouteRequest(task="chat", preferred_provider="openai", required_capabilities=["chat"])
    fallback_service.resolve(request, "req-3")
    route = fallback_service.fallback(request, "req-3", failed_provider="openai")

    assert route.provider == "local"

    skipped = [h for h in fallback_service.history("req-3") if h["outcome"] == "skipped"]
    assert any(h["provider"] == "gemini" for h in skipped)


def test_capability_filtering():
    _, routing_service = build_routing(
        capability_overrides={
            "gemini": ProviderCapabilityProfile(capabilities={"chat"}, cost=0.02, latency=0.8),
        }
    )
    fallback_service = LLMFallbackRoutingService(routing_service)
    fallback_service.configure(
        LLMFallbackPolicy(
            policy_id="p4", primary_provider="openai", fallback_providers=("gemini", "local")
        )
    )

    request = LLMRouteRequest(
        task="vision", preferred_provider="openai", required_capabilities=["vision"]
    )
    fallback_service.resolve(request, "req-4")

    with pytest.raises(NoEligibleModelError):
        fallback_service.fallback(request, "req-4", failed_provider="openai")

    skipped_providers = {
        h["provider"] for h in fallback_service.history("req-4") if h["outcome"] == "skipped"
    }
    assert skipped_providers == {"gemini", "local"}


def test_repeated_provider_prevention():
    _, routing_service = build_routing()
    fallback_service = LLMFallbackRoutingService(routing_service)
    fallback_service.configure(
        LLMFallbackPolicy(
            policy_id="p5",
            primary_provider="openai",
            fallback_providers=("gemini", "openai", "local"),
        )
    )

    request = LLMRouteRequest(task="chat", preferred_provider="openai", required_capabilities=["chat"])
    first = fallback_service.resolve(request, "req-5")
    assert first.provider == "openai"

    second = fallback_service.fallback(request, "req-5", failed_provider="openai")
    assert second.provider == "gemini"

    third = fallback_service.fallback(request, "req-5", failed_provider="gemini")
    assert third.provider == "local"

    providers_tried = [entry["provider"] for entry in fallback_service.history("req-5")]
    assert providers_tried.count("openai") == 2


def test_all_provider_failure():
    _, routing_service = build_routing()
    fallback_service = LLMFallbackRoutingService(routing_service)
    fallback_service.configure(
        LLMFallbackPolicy(
            policy_id="p6", primary_provider="openai", fallback_providers=("gemini", "local")
        )
    )

    request = LLMRouteRequest(task="chat", preferred_provider="openai", required_capabilities=["chat"])
    fallback_service.resolve(request, "req-6")
    fallback_service.fallback(request, "req-6", failed_provider="openai")
    fallback_service.fallback(request, "req-6", failed_provider="gemini")

    with pytest.raises(NoEligibleModelError):
        fallback_service.fallback(request, "req-6", failed_provider="local")

    outcomes = [entry["outcome"] for entry in fallback_service.history("req-6")]
    assert outcomes.count("failed") == 3
