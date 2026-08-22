import dataclasses

import pytest

from backend.llm import LLMRequest, LLMResponse
from backend.llm.audit import (
    DuplicateAuditRequestError,
    LLMRequestAuditService,
    UnknownAuditRequestError,
)
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.cost import LLMCostService, LLMModelPricing
from backend.llm.fallback import LLMFallbackPolicy, LLMFallbackRoutingService
from backend.llm.routing import LLMModelRoutingService, LLMRouteRequest, ProviderCapabilityProfile
from backend.llm.usage import LLMUsageService


def make_request(model="gpt-4o"):
    return LLMRequest(model=model, messages=[{"role": "user", "content": "hi"}], temperature=0.0)


def test_request_lifecycle():
    usage_service = LLMUsageService()
    audit_service = LLMRequestAuditService(usage_service)

    audit = audit_service.start(make_request(), "req-1", provider="openai")

    assert audit.request_id == "req-1"
    assert audit.provider == "openai"
    assert audit.model == "gpt-4o"
    assert audit.status == "started"
    assert audit.attempts == 1
    assert audit.completed_at is None

    completed = audit_service.complete("req-1", status="succeeded")
    assert completed.status == "succeeded"
    assert completed.completed_at is not None
    assert audit_service.get("req-1") is completed

    with pytest.raises(DuplicateAuditRequestError):
        audit_service.start(make_request(), "req-1", provider="openai")

    with pytest.raises(UnknownAuditRequestError):
        audit_service.get("does-not-exist")


def test_attempt_recording():
    usage_service = LLMUsageService()
    audit_service = LLMRequestAuditService(usage_service)

    audit_service.start(make_request(), "req-2", provider="openai")
    updated = audit_service.record_attempt("req-2", provider="openai", model="gpt-4o")

    assert updated.attempts == 2
    assert updated.provider == "openai"

    with pytest.raises(UnknownAuditRequestError):
        audit_service.record_attempt("missing", provider="openai", model="gpt-4o")


def test_fallback_history():
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="K1")
    )
    config_service.register(
        LLMProviderConfig(provider="gemini", model="gemini-1.5-pro", api_key_ref="K2")
    )

    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.03, latency=1.0)
    )
    routing_service.register_capability_profile(
        "gemini", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.02, latency=0.8)
    )

    fallback_service = LLMFallbackRoutingService(routing_service)
    fallback_service.configure(
        LLMFallbackPolicy(
            policy_id="p", primary_provider="openai", fallback_providers=("gemini",)
        )
    )

    usage_service = LLMUsageService()
    audit_service = LLMRequestAuditService(usage_service)

    route_request = LLMRouteRequest(
        task="chat", preferred_provider="openai", required_capabilities=["chat"]
    )
    primary = fallback_service.resolve(route_request, "req-3")
    audit_service.start(make_request(model=primary.model), "req-3", provider=primary.provider)

    next_route = fallback_service.fallback(route_request, "req-3", failed_provider=primary.provider)
    audit_service.record_attempt("req-3", provider=next_route.provider, model=next_route.model)

    trail = audit_service.history("req-3")

    assert [entry.provider for entry in trail] == ["openai", "gemini"]
    assert [entry.model for entry in trail] == ["gpt-4o", "gemini-1.5-pro"]
    assert trail[-1].attempts == 2


def test_usage_cost_aggregation():
    usage_service = LLMUsageService()
    cost_service = LLMCostService(usage_service)
    cost_service.register_pricing(
        LLMModelPricing(provider="openai", model="gpt-4o", input_cost=0.01, output_cost=0.02)
    )

    audit_service = LLMRequestAuditService(usage_service, cost_service)
    audit_service.start(make_request(), "req-4", provider="openai")

    response = LLMResponse(
        content="hi there",
        model="gpt-4o",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        finish_reason="stop",
    )
    usage_service.record(response, "req-4", "openai")

    completed = audit_service.complete("req-4", status="succeeded")

    assert completed.total_tokens == 15
    assert completed.total_cost == pytest.approx(10 * 0.01 + 5 * 0.02)


def test_completion_state():
    usage_service = LLMUsageService()
    audit_service = LLMRequestAuditService(usage_service)

    audit_service.start(make_request(), "req-5", provider="openai")

    with pytest.raises(ValueError):
        audit_service.complete("req-5", status="")

    completed = audit_service.complete("req-5", status="failed")
    assert completed.status == "failed"
    assert completed.completed_at is not None

    recompleted = audit_service.complete("req-5", status="succeeded")
    assert recompleted.status == "succeeded"
    assert audit_service.get("req-5") is recompleted
    assert len(audit_service.history("req-5")) == 3


def test_immutable_audit_record():
    usage_service = LLMUsageService()
    audit_service = LLMRequestAuditService(usage_service)

    audit = audit_service.start(make_request(), "req-6", provider="openai")

    with pytest.raises(dataclasses.FrozenInstanceError):
        audit.status = "tampered"

    updated = audit_service.record_attempt("req-6", provider="openai", model="gpt-4o")
    assert audit.attempts == 1
    assert updated.attempts == 2
    assert updated is not audit

    trail = audit_service.history("req-6")
    trail.append("not real")
    assert len(audit_service.history("req-6")) == 2
