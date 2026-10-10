import pytest

from backend.agent_capability_compatibility import LLMAgentCapabilityCompatibility
from backend.agent_capability_contracts import LLMAgentCapabilityContract, LLMAgentCapabilityContractService
from backend.agent_capability_dependencies import LLMAgentCapabilityDependencyService
from backend.agent_capability_execution import LLMAgentCapabilityExecutionService as ExecutionRecordService
from backend.agent_capability_execution_control import LLMAgentCapabilityExecutionControl
from backend.agent_capability_execution_lifecycle import (
    REJECTED_POLICY_DENIED,
    SUCCEEDED,
    LLMAgentCapabilityExecutionLifecycleService,
)
from backend.agent_capability_execution_policy import LLMAgentCapabilityExecutionPolicy
from backend.agent_capability_execution_validation import LLMAgentCapabilityExecutionValidator
from backend.agent_capability_orchestration import (
    ACTION_CANCEL,
    ACTION_CHECK_TIMEOUT,
    CapabilityPreparationResult,
    InvalidCapabilityOrchestrationError,
    LLMAgentCapabilityOrchestrator,
)
from backend.agent_capability_registry import LLMAgentCapability, LLMAgentCapabilityRegistry
from backend.agent_capability_resolution import LLMAgentCapabilityResolver
from backend.agent_capability_selection import LLMAgentCapabilitySelector
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyService

_SCHEMA = {"type": "object", "properties": {}, "required": []}


def _build():
    registry = LLMAgentCapabilityRegistry()
    policy_service = LLMAgentPolicyService()
    resolver = LLMAgentCapabilityResolver(registry, policy_service=policy_service)
    contracts = LLMAgentCapabilityContractService(registry)
    deps = LLMAgentCapabilityDependencyService(registry)
    compatibility = LLMAgentCapabilityCompatibility(resolver, contracts, deps)
    selector = LLMAgentCapabilitySelector(registry, resolver, compatibility)

    execution_records = ExecutionRecordService()
    execution_validator = LLMAgentCapabilityExecutionValidator(contracts)
    execution_policy = LLMAgentCapabilityExecutionPolicy(policy_service)

    calls = []

    def executor(capability_id, input_payload, context):
        calls.append((capability_id, input_payload, context))
        return {}

    execution_lifecycle = LLMAgentCapabilityExecutionLifecycleService(
        registry, execution_records, execution_validator, execution_policy, executor
    )
    execution_control = LLMAgentCapabilityExecutionControl(execution_records)

    orchestrator = LLMAgentCapabilityOrchestrator(
        registry, resolver, deps, compatibility, selector, execution_lifecycle, execution_control,
    )

    return {
        "registry": registry,
        "policy_service": policy_service,
        "contracts": contracts,
        "deps": deps,
        "compatibility": compatibility,
        "selector": selector,
        "execution_records": execution_records,
        "execution_lifecycle": execution_lifecycle,
        "execution_control": execution_control,
        "orchestrator": orchestrator,
        "calls": calls,
    }


def _register(env, capability_id="web-search", category="retrieval", allow=True):
    env["registry"].register(
        LLMAgentCapability(capability_id=capability_id, name=capability_id, description="d", category=category)
    )
    env["contracts"].register(
        LLMAgentCapabilityContract(
            capability_id=capability_id, version="1.0.0", input_schema=_SCHEMA, output_schema=_SCHEMA,
        )
    )
    if allow:
        env["policy_service"].create(
            "scope-1",
            f"allow-{capability_id}",
            [{"rule_id": "allow-it", "effect": ALLOW, "match": {"capability_id": capability_id}}],
        )


def test_preparation_returns_usable_capabilities():
    env = _build()
    _register(env)

    result = env["orchestrator"].prepare("agent-1", "scope-1", {"description": "search the web"})

    assert isinstance(result, CapabilityPreparationResult)
    assert "web-search" in result.resolved_capabilities
    assert "web-search" in result.selected_capabilities
    assert result.compatibility["web-search"].compatible is True
    assert result.dependency_status["web-search"].valid is True
    assert result.rejections == {}


def test_invalid_dependencies_prevent_selection():
    env = _build()
    _register(env, capability_id="web-search")
    _register(env, capability_id="index")
    env["deps"].add_dependency("web-search", "index")
    env["registry"].archive("index")

    result = env["orchestrator"].prepare("agent-1", "scope-1", {"description": "search"})

    assert "web-search" in result.resolved_capabilities
    assert "web-search" not in result.selected_capabilities
    assert result.dependency_status["web-search"].valid is False
    assert "web-search" in result.rejections


def test_incompatible_capabilities_are_excluded():
    env = _build()
    # registered but no contract -> incompatible (CHECK_CONTRACT fails)
    env["registry"].register(
        LLMAgentCapability(capability_id="no-contract", name="n", description="d", category="retrieval")
    )
    env["policy_service"].create(
        "scope-1", "allow-no-contract",
        [{"rule_id": "allow-it", "effect": ALLOW, "match": {"capability_id": "no-contract"}}],
    )

    result = env["orchestrator"].prepare("agent-1", "scope-1", {"description": "x"})

    assert "no-contract" in result.resolved_capabilities
    assert "no-contract" not in result.selected_capabilities
    assert result.compatibility["no-contract"].compatible is False
    assert "no-contract" in result.rejections


def test_selected_execution_delegates_to_existing_lifecycle():
    env = _build()
    _register(env)

    result = env["orchestrator"].execute_selected("agent-1", "scope-1", "web-search", {})

    assert result.status == SUCCEEDED
    assert len(env["calls"]) == 1
    assert env["calls"][0][0] == "web-search"

    direct = env["execution_lifecycle"].execute("agent-1", "web-search", "scope-1", {})
    assert direct.status == SUCCEEDED
    assert len(env["calls"]) == 2


def test_policy_failure_propagates_through_execute_selected():
    env = _build()
    env["registry"].register(
        LLMAgentCapability(capability_id="web-search", name="w", description="d", category="retrieval")
    )
    env["contracts"].register(
        LLMAgentCapabilityContract(
            capability_id="web-search", version="1.0.0", input_schema=_SCHEMA, output_schema=_SCHEMA,
        )
    )
    env["policy_service"].create(
        "scope-1", "deny-it", [{"rule_id": "deny-it", "effect": DENY, "match": {"capability_id": "web-search"}}]
    )

    result = env["orchestrator"].execute_selected("agent-1", "scope-1", "web-search", {})

    assert result.status == REJECTED_POLICY_DENIED
    assert env["calls"] == []


def test_control_delegates_to_existing_cancellation_and_timeout_behavior():
    env = _build()
    _register(env)
    execution = env["execution_records"].start("agent-1", "web-search", "1.0.0", "scope-1")

    result = env["orchestrator"].control(execution.execution_id, ACTION_CANCEL)

    record = env["execution_records"].get(execution.execution_id)
    assert record.status == "FAILED"
    assert result.action == "CANCELLED"
    assert result.execution_id == execution.execution_id

    execution2 = env["execution_records"].start("agent-1", "web-search", "1.0.0", "scope-1")
    timeout_result = env["orchestrator"].control(execution2.execution_id, ACTION_CHECK_TIMEOUT)
    assert timeout_result.action == "NONE"  # no deadline configured on this control instance


def test_invalid_control_action_raises():
    env = _build()
    _register(env)
    execution = env["execution_records"].start("agent-1", "web-search", "1.0.0", "scope-1")

    with pytest.raises(InvalidCapabilityOrchestrationError):
        env["orchestrator"].control(execution.execution_id, "retry")


def test_no_domain_logic_is_duplicated():
    env = _build()
    _register(env)

    prepared = env["orchestrator"].prepare("agent-1", "scope-1", {"description": "search"})

    direct_compat = env["compatibility"].check("web-search", "agent-1", "scope-1", {"description": "search"})
    direct_deps = env["deps"].validate_dependencies(["web-search"])

    assert prepared.compatibility["web-search"] == direct_compat
    assert prepared.dependency_status["web-search"] == direct_deps
