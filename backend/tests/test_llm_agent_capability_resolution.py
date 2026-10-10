import pytest

from backend.agent_capability_registry import LLMAgentCapability, LLMAgentCapabilityRegistry
from backend.agent_capability_resolution import (
    InvalidCapabilityResolutionError,
    LLMAgentCapabilityResolver,
    ResolvedAgentCapabilities,
)
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyService


def _capability(**overrides):
    fields = {
        "capability_id": "web-search",
        "name": "Web Search",
        "description": "Search the public web",
        "category": "retrieval",
        "version": "1.0.0",
    }
    fields.update(overrides)
    return LLMAgentCapability(**fields)


def _registry_with(*capabilities):
    registry = LLMAgentCapabilityRegistry()
    for capability in capabilities:
        registry.register(capability)
    return registry


def test_active_capabilities_resolve_by_default():
    registry = _registry_with(_capability())
    resolver = LLMAgentCapabilityResolver(registry)

    result = resolver.resolve("agent-1", "scope-1")

    assert isinstance(result, ResolvedAgentCapabilities)
    assert result.agent_id == "agent-1"
    assert result.scope_id == "scope-1"
    assert [c.capability_id for c in result.capabilities] == ["web-search"]
    assert result.excluded_capabilities == []
    assert "web-search" in result.resolution_reasons


def test_archived_capabilities_are_excluded():
    registry = _registry_with(_capability(), _capability(capability_id="code-exec", category="code_execution"))
    registry.archive("code-exec")
    resolver = LLMAgentCapabilityResolver(registry)

    result = resolver.resolve("agent-1", "scope-1")

    assert [c.capability_id for c in result.capabilities] == ["web-search"]
    assert [c.capability_id for c in result.excluded_capabilities] == ["code-exec"]
    assert "archived" in result.resolution_reasons["code-exec"]


def test_scope_restrictions_are_respected():
    registry = _registry_with(_capability())
    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1",
        "deny-web-search",
        [{"rule_id": "deny-it", "effect": DENY, "match": {"capability_id": "web-search"}}],
    )
    resolver = LLMAgentCapabilityResolver(registry, policy_service=policy_service)

    denied_scope = resolver.resolve("agent-1", "scope-1")
    assert denied_scope.capabilities == []
    assert [c.capability_id for c in denied_scope.excluded_capabilities] == ["web-search"]
    assert "denied" in denied_scope.resolution_reasons["web-search"]

    # a different, unrestricted scope is unaffected
    other_scope = resolver.resolve("agent-1", "scope-2")
    assert [c.capability_id for c in other_scope.capabilities] == ["web-search"]


def test_agent_specific_restrictions_are_respected_when_supported():
    registry = _registry_with(_capability())
    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1",
        "deny-agent-2",
        [{"rule_id": "deny-it", "effect": DENY, "match": {"agent_id": "agent-2", "capability_id": "web-search"}}],
    )
    resolver = LLMAgentCapabilityResolver(registry, policy_service=policy_service)

    blocked = resolver.resolve("agent-2", "scope-1")
    assert blocked.capabilities == []
    assert [c.capability_id for c in blocked.excluded_capabilities] == ["web-search"]

    allowed = resolver.resolve("agent-1", "scope-1")
    assert [c.capability_id for c in allowed.capabilities] == ["web-search"]


def test_no_policy_service_configured_excludes_nothing_by_policy():
    registry = _registry_with(_capability())
    resolver = LLMAgentCapabilityResolver(registry)

    result = resolver.resolve("agent-1", "scope-1")
    assert [c.capability_id for c in result.capabilities] == ["web-search"]


def test_explicit_allow_rule_does_not_change_default_inclusion():
    registry = _registry_with(_capability())
    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1",
        "allow-web-search",
        [{"rule_id": "allow-it", "effect": ALLOW, "match": {"capability_id": "web-search"}}],
    )
    resolver = LLMAgentCapabilityResolver(registry, policy_service=policy_service)

    result = resolver.resolve("agent-1", "scope-1")
    assert [c.capability_id for c in result.capabilities] == ["web-search"]


def test_inclusion_exclusion_reasons_are_deterministic():
    registry = _registry_with(_capability(), _capability(capability_id="code-exec", category="code_execution"))
    registry.archive("code-exec")
    resolver = LLMAgentCapabilityResolver(registry)

    first = resolver.resolve("agent-1", "scope-1")
    second = resolver.resolve("agent-1", "scope-1")

    assert first.resolution_reasons == second.resolution_reasons
    assert [c.capability_id for c in first.capabilities] == [c.capability_id for c in second.capabilities]
    assert [c.capability_id for c in first.excluded_capabilities] == [
        c.capability_id for c in second.excluded_capabilities
    ]


def test_resolution_is_side_effect_free():
    registry = _registry_with(_capability())
    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1", "deny-web-search", [{"rule_id": "deny-it", "effect": DENY, "match": {"capability_id": "web-search"}}],
    )
    resolver = LLMAgentCapabilityResolver(registry, policy_service=policy_service)

    before = registry.get("web-search")
    resolver.resolve("agent-1", "scope-1")
    after = registry.get("web-search")

    assert before == after
    assert before.status == after.status
    # the registry's own listing is unaffected by resolution
    assert [c.capability_id for c in registry.list()] == ["web-search"]


def test_resolve_validation():
    registry = _registry_with(_capability())
    resolver = LLMAgentCapabilityResolver(registry)

    with pytest.raises(InvalidCapabilityResolutionError):
        resolver.resolve("", "scope-1")
    with pytest.raises(InvalidCapabilityResolutionError):
        resolver.resolve("agent-1", "")
    with pytest.raises(InvalidCapabilityResolutionError):
        resolver.resolve("agent-1", "scope-1", context="not-a-dict")


def test_context_cannot_override_identity_fields():
    registry = _registry_with(_capability())
    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1", "deny-web-search", [{"rule_id": "deny-it", "effect": DENY, "match": {"capability_id": "web-search"}}],
    )
    resolver = LLMAgentCapabilityResolver(registry, policy_service=policy_service)

    result = resolver.resolve("agent-1", "scope-1", context={"capability_id": "spoofed", "role": "admin"})
    assert result.capabilities == []
    assert [c.capability_id for c in result.excluded_capabilities] == ["web-search"]
