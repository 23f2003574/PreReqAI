import pytest

from backend.agent_capability_compatibility import (
    CHECK_AVAILABILITY,
    CHECK_CONTRACT,
    CHECK_DEPENDENCIES,
    CHECK_EXISTENCE,
    CHECK_REQUIRED_CONTEXT,
    InvalidCapabilityCompatibilityError,
    LLMAgentCapabilityCompatibility,
)
from backend.agent_capability_contracts import LLMAgentCapabilityContract, LLMAgentCapabilityContractService
from backend.agent_capability_dependencies import LLMAgentCapabilityDependencyService
from backend.agent_capability_registry import LLMAgentCapability, LLMAgentCapabilityRegistry
from backend.agent_capability_resolution import InvalidCapabilityResolutionError, LLMAgentCapabilityResolver
from backend.agent_policy_engine import DENY, LLMAgentPolicyService

_SCHEMA = {"type": "object", "properties": {}, "required": []}


def _capability(capability_id="web-search", metadata=None):
    return LLMAgentCapability(
        capability_id=capability_id,
        name=capability_id,
        description=f"{capability_id} description",
        category="retrieval",
        metadata=metadata or {},
    )


def _contract(capability_id="web-search", **overrides):
    fields = {
        "capability_id": capability_id,
        "version": "1.0.0",
        "input_schema": _SCHEMA,
        "output_schema": _SCHEMA,
    }
    fields.update(overrides)
    return LLMAgentCapabilityContract(**fields)


def _build(registry=None, policy_service=None):
    registry = registry or LLMAgentCapabilityRegistry()
    resolver = LLMAgentCapabilityResolver(registry, policy_service=policy_service)
    contract_service = LLMAgentCapabilityContractService(registry)
    dependency_service = LLMAgentCapabilityDependencyService(registry)
    checker = LLMAgentCapabilityCompatibility(resolver, contract_service, dependency_service)
    return registry, contract_service, dependency_service, checker


def test_compatible_capability_passes():
    registry, contracts, deps, checker = _build()
    registry.register(_capability())
    contracts.register(_contract())

    result = checker.check("web-search", "agent-1", "scope-1")

    assert result.compatible is True
    assert result.failed_checks == []
    assert result.capability_id == "web-search"
    assert result.agent_id == "agent-1"
    assert result.scope_id == "scope-1"
    assert len(result.reasons) > 0


def test_unknown_capability_fails():
    _registry, _contracts, _deps, checker = _build()

    result = checker.check("nonexistent", "agent-1", "scope-1")

    assert result.compatible is False
    assert result.failed_checks == [CHECK_EXISTENCE]


def test_archived_capability_is_unavailable_and_fails():
    registry, contracts, deps, checker = _build()
    registry.register(_capability())
    contracts.register(_contract())
    registry.archive("web-search")

    result = checker.check("web-search", "agent-1", "scope-1")

    assert result.compatible is False
    assert CHECK_AVAILABILITY in result.failed_checks


def test_policy_denial_is_reported_as_unavailable():
    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1",
        "deny-web-search",
        [{"rule_id": "deny-it", "effect": DENY, "match": {"capability_id": "web-search"}}],
    )
    registry, contracts, deps, checker = _build(policy_service=policy_service)
    registry.register(_capability())
    contracts.register(_contract())

    result = checker.check("web-search", "agent-1", "scope-1")

    assert result.compatible is False
    assert CHECK_AVAILABILITY in result.failed_checks
    assert any("denied" in reason for reason in result.reasons)


def test_missing_contract_fails():
    registry, _contracts, _deps, checker = _build()
    registry.register(_capability())

    result = checker.check("web-search", "agent-1", "scope-1")

    assert result.compatible is False
    assert CHECK_CONTRACT in result.failed_checks


def test_unavailable_dependency_fails():
    registry, contracts, deps, checker = _build()
    registry.register(_capability())
    registry.register(_capability("needs-index"))
    contracts.register(_contract())
    deps.add_dependency("web-search", "needs-index")
    registry.archive("needs-index")

    result = checker.check("web-search", "agent-1", "scope-1")

    assert result.compatible is False
    assert CHECK_DEPENDENCIES in result.failed_checks


def test_missing_required_context_is_reported():
    registry, contracts, deps, checker = _build()
    registry.register(_capability())
    contracts.register(_contract(required_context=["user_id"]))

    result = checker.check("web-search", "agent-1", "scope-1")

    assert result.compatible is False
    assert CHECK_REQUIRED_CONTEXT in result.failed_checks
    assert any("user_id" in reason for reason in result.reasons)

    satisfied = checker.check("web-search", "agent-1", "scope-1", context={"user_id": "u1"})
    assert satisfied.compatible is True


def test_warnings_do_not_become_blocking_failures():
    registry, contracts, deps, checker = _build()
    registry.register(_capability(metadata={"warnings": ["uses a beta provider"]}))
    contracts.register(_contract())

    result = checker.check("web-search", "agent-1", "scope-1")

    assert result.compatible is True
    assert result.failed_checks == []
    assert "uses a beta provider" in result.warnings


def test_repeated_checks_produce_the_same_result():
    registry, contracts, deps, checker = _build()
    registry.register(_capability())
    contracts.register(_contract(required_context=["user_id"]))

    first = checker.check("web-search", "agent-1", "scope-1", context={"user_id": "u1"})
    second = checker.check("web-search", "agent-1", "scope-1", context={"user_id": "u1"})

    assert first == second


def test_check_is_side_effect_free():
    registry, contracts, deps, checker = _build()
    registry.register(_capability())
    registry.register(_capability("helper"))
    contracts.register(_contract())
    deps.add_dependency("web-search", "helper")

    before_capability = registry.get("web-search")
    before_dependencies = deps.get_dependencies("web-search")
    checker.check("web-search", "agent-1", "scope-1")
    after_capability = registry.get("web-search")

    assert before_capability == after_capability
    assert deps.get_dependencies("web-search") == before_dependencies


def test_validation_errors():
    _registry, _contracts, _deps, checker = _build()

    with pytest.raises(InvalidCapabilityCompatibilityError):
        checker.check("", "agent-1", "scope-1")
    with pytest.raises(InvalidCapabilityResolutionError):
        checker.check("web-search", "", "scope-1")
    with pytest.raises(InvalidCapabilityResolutionError):
        checker.check("web-search", "agent-1", "scope-1", context="not-a-dict")
