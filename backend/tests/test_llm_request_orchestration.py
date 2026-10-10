import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.audit import LLMRequestAuditService
from backend.llm.budget import LLMBudgetService
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextItem, LLMContextService
from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.fallback import LLMFallbackPolicy, LLMFallbackRoutingService
from backend.llm.orchestration import LLMRequestOrchestrationService, UnknownDecisionError
from backend.llm.response_cache import LLMResponseCacheService
from backend.llm.retry import LLMRetryPolicy, LLMRetryService, TransientLLMError
from backend.llm.routing import LLMModelRoutingService, LLMRouteRequest, ProviderCapabilityProfile
from backend.llm.usage import LLMUsageService

MODELS = {"openai": "gpt-4o", "gemini": "gemini-1.5-pro", "local": "llama3"}


class ScriptedProvider(LLMProvider):
    """A real Commit #1 LLMProvider that replays a scripted outcome per call."""

    def __init__(self, name, script):
        self._name = name
        self._script = list(script)
        self.calls = 0

    def models(self):
        return [MODELS[self._name]]

    def complete(self, request):
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request):
        raise NotImplementedError


def make_response(model, content="ok"):
    return LLMResponse(
        content=content,
        model=model,
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        finish_reason="stop",
    )


def build_env(
    provider_scripts,
    disabled=None,
    with_budget=False,
    with_retry=False,
    with_fallback=True,
):
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
    for provider in MODELS:
        routing_service.register_capability_profile(
            provider, ProviderCapabilityProfile(capabilities={"chat"}, cost=0.02, latency=1.0)
        )

    context_service = LLMContextService()
    cache_service = LLMResponseCacheService()
    budget_service = LLMBudgetService() if with_budget else None
    retry_service = LLMRetryService() if with_retry else None

    fallback_service = None
    if with_fallback:
        fallback_service = LLMFallbackRoutingService(routing_service)
        fallback_service.configure(
            LLMFallbackPolicy(
                policy_id="p", primary_provider="openai", fallback_providers=("gemini", "local")
            )
        )

    usage_service = LLMUsageService()
    cost_service = LLMCostService(usage_service)
    for provider, model in MODELS.items():
        cost_service.register_pricing(
            LLMModelPricing(provider=provider, model=model, input_cost=0.01, output_cost=0.02)
        )

    audit_service = LLMRequestAuditService(usage_service, cost_service)

    providers = {name: ScriptedProvider(name, script) for name, script in provider_scripts.items()}

    orchestrator = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers=providers,
        budget_service=budget_service,
        cache_service=cache_service,
        retry_service=retry_service,
        fallback_service=fallback_service,
        usage_service=usage_service,
        cost_service=cost_service,
        audit_service=audit_service,
    )

    return {
        "orchestrator": orchestrator,
        "context_service": context_service,
        "cache_service": cache_service,
        "budget_service": budget_service,
        "retry_service": retry_service,
        "fallback_service": fallback_service,
        "usage_service": usage_service,
        "cost_service": cost_service,
        "audit_service": audit_service,
        "providers": providers,
    }


def seed_context(env, context_id, content="hi"):
    env["context_service"].create(context_id)
    env["context_service"].add(context_id, LLMContextItem(type="user", content=content, priority=1))


def make_route_request(preferred="openai"):
    return LLMRouteRequest(task="chat", preferred_provider=preferred, required_capabilities=["chat"])


def test_successful_request():
    env = build_env({"openai": [make_response("gpt-4o", content="hello")]})
    seed_context(env, "req-1")

    response, decision = env["orchestrator"].execute(make_route_request(), "req-1", "req-1")

    assert response.content == "hello"
    assert decision.allowed is True
    assert decision.provider == "openai"
    assert decision.model == "gpt-4o"
    assert decision.cached is False


def test_cache_hit():
    env = build_env({"openai": [make_response("gpt-4o", content="hello")]})
    seed_context(env, "req-2")
    env["orchestrator"].execute(make_route_request(), "req-2", "req-2")
    assert env["providers"]["openai"].calls == 1

    seed_context(env, "req-2b")
    response, decision = env["orchestrator"].execute(make_route_request(), "req-2b", "req-2b")

    assert decision.cached is True
    assert response.content == "hello"
    assert env["providers"]["openai"].calls == 1


def test_budget_rejection():
    env = build_env({"openai": [make_response("gpt-4o")]}, with_budget=True)
    env["budget_service"].configure("ws-1", max_tokens=10, max_cost=None)
    env["budget_service"].consume("ws-1", tokens=10, cost=0.0)
    seed_context(env, "req-3")

    response, decision = env["orchestrator"].execute(
        make_route_request(), "req-3", "req-3", budget_scope_id="ws-1", estimated_tokens=5
    )

    assert response is None
    assert decision.allowed is False
    assert "budget" in decision.reason.lower()
    assert env["providers"]["openai"].calls == 0


def test_retry_path():
    env = build_env(
        {"openai": [TransientLLMError("timeout"), make_response("gpt-4o", content="recovered")]},
        with_retry=True,
    )
    env["retry_service"].configure(
        "req-4", LLMRetryPolicy(policy_id="p", max_attempts=3, backoff_seconds=0.001)
    )
    seed_context(env, "req-4")

    response, decision = env["orchestrator"].execute(make_route_request(), "req-4", "req-4")

    assert response.content == "recovered"
    assert decision.allowed is True
    assert decision.provider == "openai"
    assert env["providers"]["openai"].calls == 2


def test_provider_fallback():
    env = build_env(
        {
            "openai": [RuntimeError("simulated failure")],
            "gemini": [make_response("gemini-1.5-pro", content="from gemini")],
        }
    )
    seed_context(env, "req-5")

    response, decision = env["orchestrator"].execute(make_route_request(), "req-5", "req-5")

    assert response.content == "from gemini"
    assert decision.provider == "gemini"
    assert decision.model == "gemini-1.5-pro"

    history = env["fallback_service"].history("req-5")
    assert [h["provider"] for h in history] == ["openai", "openai", "gemini"]


def test_usage_cost_recording():
    env = build_env({"openai": [make_response("gpt-4o")]})
    seed_context(env, "req-6")

    env["orchestrator"].execute(make_route_request(), "req-6", "req-6")

    usage_records = env["usage_service"].get("req-6")
    assert len(usage_records) == 1
    assert usage_records[0].total_tokens == 15

    estimate = env["cost_service"].estimate("req-6")
    assert estimate.total_cost == pytest.approx(10 * 0.01 + 5 * 0.02)


def test_audit_completion():
    env = build_env({"openai": [make_response("gpt-4o")]})
    seed_context(env, "req-7")

    env["orchestrator"].execute(make_route_request(), "req-7", "req-7")

    audit = env["audit_service"].get("req-7")
    assert audit.status == "succeeded"
    assert audit.completed_at is not None
    assert audit.provider == "openai"
    assert audit.total_tokens == 15


def test_deterministic_decision():
    env = build_env({"openai": [make_response("gpt-4o")]})
    seed_context(env, "req-8")

    _, decision = env["orchestrator"].execute(make_route_request(), "req-8", "req-8")

    fetched = env["orchestrator"].decision("req-8")
    fetched_again = env["orchestrator"].decision("req-8")

    assert fetched is decision
    assert fetched is fetched_again

    with pytest.raises(UnknownDecisionError):
        env["orchestrator"].decision("does-not-exist")
