import time

import pytest

from backend.agent_capability_compatibility import LLMAgentCapabilityCompatibility
from backend.agent_capability_contracts import LLMAgentCapabilityContract, LLMAgentCapabilityContractService
from backend.agent_capability_dependencies import LLMAgentCapabilityDependencyService
from backend.agent_capability_registry import LLMAgentCapability, LLMAgentCapabilityRegistry
from backend.agent_capability_resolution import LLMAgentCapabilityResolver
from backend.agent_capability_selection import (
    InvalidCapabilitySelectionError,
    LLMAgentCapabilitySelector,
)
from backend.agent_policy_engine import DENY, LLMAgentPolicyService

_SCHEMA = {"type": "object", "properties": {}, "required": []}


def _capability(capability_id, name=None, description=None, category="retrieval"):
    return LLMAgentCapability(
        capability_id=capability_id,
        name=name or capability_id,
        description=description or f"{capability_id} description",
        category=category,
    )


def _contract(capability_id):
    return LLMAgentCapabilityContract(
        capability_id=capability_id, version="1.0.0", input_schema=_SCHEMA, output_schema=_SCHEMA,
    )


def _build(policy_service=None):
    registry = LLMAgentCapabilityRegistry()
    resolver = LLMAgentCapabilityResolver(registry, policy_service=policy_service)
    contracts = LLMAgentCapabilityContractService(registry)
    deps = LLMAgentCapabilityDependencyService(registry)
    compatibility = LLMAgentCapabilityCompatibility(resolver, contracts, deps)
    selector = LLMAgentCapabilitySelector(registry, resolver, compatibility)
    return registry, contracts, deps, selector


def test_selects_a_valid_capability_for_a_matching_task():
    registry, contracts, _deps, selector = _build()
    registry.register(_capability("web-search", name="Web Search", description="search the public web"))
    contracts.register(_contract("web-search"))

    result = selector.select("agent-1", "scope-1", {"description": "please search the web for transformers"})

    assert result.selected_capabilities == ["web-search"]
    assert result.rejected_capabilities == []
    assert "web-search" in result.selection_reasons


def test_rejects_incompatible_capabilities():
    registry, contracts, _deps, selector = _build()
    registry.register(_capability("web-search"))
    contracts.register(_contract("web-search"))
    registry.archive("web-search")

    result = selector.select("agent-1", "scope-1", {"description": "search the web"})

    assert result.selected_capabilities == []
    assert result.rejected_capabilities == []  # archived capabilities never appear as resolver candidates at all


def test_rejects_incompatible_explicit_candidate():
    registry, contracts, _deps, selector = _build()
    registry.register(_capability("web-search"))
    contracts.register(_contract("web-search"))
    registry.archive("web-search")

    result = selector.select("agent-1", "scope-1", {}, candidates=["web-search"])

    assert result.selected_capabilities == []
    assert result.rejected_capabilities == ["web-search"]
    assert "rejected" in result.selection_reasons["web-search"]


def test_rejects_unsatisfied_dependencies():
    registry, contracts, deps, selector = _build()
    registry.register(_capability("web-search"))
    registry.register(_capability("index"))
    contracts.register(_contract("web-search"))
    deps.add_dependency("web-search", "index")
    registry.archive("index")

    result = selector.select("agent-1", "scope-1", {"description": "search"})

    assert "web-search" in result.rejected_capabilities
    assert result.selected_capabilities == []


def test_policy_restriction_rejects_via_explicit_candidates():
    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1", "deny-web-search", [{"rule_id": "deny-it", "effect": DENY, "match": {"capability_id": "web-search"}}],
    )
    registry, contracts, _deps, selector = _build(policy_service=policy_service)
    registry.register(_capability("web-search"))
    contracts.register(_contract("web-search"))

    result = selector.select("agent-1", "scope-1", {}, candidates=["web-search"])

    assert result.selected_capabilities == []
    assert result.rejected_capabilities == ["web-search"]


def test_handles_explicit_candidate_subsets():
    registry, contracts, _deps, selector = _build()
    registry.register(_capability("web-search", description="search the web"))
    registry.register(_capability("code-exec", category="code_execution", description="run code"))
    contracts.register(_contract("web-search"))
    contracts.register(_contract("code-exec"))

    result = selector.select("agent-1", "scope-1", {"description": "search the web"}, candidates=["web-search"])

    assert result.selected_capabilities == ["web-search"]
    assert "code-exec" not in result.selection_reasons


def test_deterministic_tie_breaking():
    registry, contracts, _deps, selector = _build()
    registry.register(_capability("a-search", description="search"))
    time.sleep(0.001)
    registry.register(_capability("b-search", description="search"))
    contracts.register(_contract("a-search"))
    contracts.register(_contract("b-search"))

    result = selector.select("agent-1", "scope-1", {"description": "search"})

    # equal relevance -- most-recently-registered wins the tie
    assert result.selected_capabilities == ["b-search", "a-search"]

    # repeated calls are stable
    again = selector.select("agent-1", "scope-1", {"description": "search"})
    assert again.selected_capabilities == result.selected_capabilities


def test_selection_reasons_are_populated():
    registry, contracts, _deps, selector = _build()
    registry.register(_capability("web-search", description="search the web"))
    contracts.register(_contract("web-search"))

    result = selector.select("agent-1", "scope-1", {"description": "search the web"})

    assert result.selection_reasons["web-search"]
    assert "relevance" in result.selection_reasons["web-search"]


def test_no_execution_or_state_mutation_occurs():
    registry, contracts, deps, selector = _build()
    registry.register(_capability("web-search", description="search the web"))
    contracts.register(_contract("web-search"))

    before = registry.get("web-search")
    selector.select("agent-1", "scope-1", {"description": "search the web"})
    after = registry.get("web-search")

    assert before == after


def test_validation_errors():
    _registry, _contracts, _deps, selector = _build()

    with pytest.raises(InvalidCapabilitySelectionError):
        selector.select("", "scope-1", {})
    with pytest.raises(InvalidCapabilitySelectionError):
        selector.select("agent-1", "", {})
    with pytest.raises(InvalidCapabilitySelectionError):
        selector.select("agent-1", "scope-1", "not-a-dict")
    with pytest.raises(InvalidCapabilitySelectionError):
        selector.select("agent-1", "scope-1", {}, candidates="not-a-list")
    with pytest.raises(InvalidCapabilitySelectionError):
        selector.select("agent-1", "scope-1", {}, candidates=[1, 2])
