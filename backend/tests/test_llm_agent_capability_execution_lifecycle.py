import pytest

from backend.agent_capability_contracts import LLMAgentCapabilityContract, LLMAgentCapabilityContractService
from backend.agent_capability_execution import LLMAgentCapabilityExecutionService as ExecutionRecordService
from backend.agent_capability_execution import FAILED as RECORD_FAILED
from backend.agent_capability_execution import SUCCEEDED as RECORD_SUCCEEDED
from backend.agent_capability_execution_lifecycle import (
    REJECTED_INVALID_INPUT,
    REJECTED_INVALID_OUTPUT,
    REJECTED_POLICY_DENIED,
    REJECTED_UNKNOWN_CAPABILITY,
    SUCCEEDED,
    FAILED,
    CapabilityExecutionResult,
    InvalidCapabilityExecutionLifecycleError,
    LLMAgentCapabilityExecutionLifecycleService,
)
from backend.agent_capability_execution_policy import LLMAgentCapabilityExecutionPolicy
from backend.agent_capability_execution_validation import LLMAgentCapabilityExecutionValidator
from backend.agent_capability_registry import LLMAgentCapability, LLMAgentCapabilityRegistry
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyService

_INPUT_SCHEMA = {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
_OUTPUT_SCHEMA = {"type": "object", "properties": {"results": {"type": "array"}}, "required": ["results"]}


def _build(executor=None):
    registry = LLMAgentCapabilityRegistry()
    contracts = LLMAgentCapabilityContractService(registry)
    execution_records = ExecutionRecordService()
    execution_validator = LLMAgentCapabilityExecutionValidator(contracts)
    policy_service = LLMAgentPolicyService()
    execution_policy = LLMAgentCapabilityExecutionPolicy(policy_service)

    calls = []

    def default_executor(capability_id, input_payload, context):
        calls.append((capability_id, input_payload, context))
        return {"results": [1, 2, 3]}

    lifecycle = LLMAgentCapabilityExecutionLifecycleService(
        registry, execution_records, execution_validator, execution_policy, executor or default_executor,
    )
    return {
        "registry": registry,
        "contracts": contracts,
        "execution_records": execution_records,
        "policy_service": policy_service,
        "lifecycle": lifecycle,
        "calls": calls,
    }


def _register(env, capability_id="web-search", version="1.0.0", allow=True):
    env["registry"].register(
        LLMAgentCapability(
            capability_id=capability_id, name=capability_id, description="d", category="retrieval", version=version,
        )
    )
    env["contracts"].register(
        LLMAgentCapabilityContract(
            capability_id=capability_id, version=version, input_schema=_INPUT_SCHEMA, output_schema=_OUTPUT_SCHEMA,
        )
    )
    if allow:
        env["policy_service"].create(
            "scope-1", "allow-it", [{"rule_id": "allow-it", "effect": ALLOW, "match": {"capability_id": capability_id}}]
        )


def test_successful_execution_reaches_completed_state():
    env = _build()
    _register(env)

    result = env["lifecycle"].execute("agent-1", "web-search", "scope-1", {"query": "x"})

    assert isinstance(result, CapabilityExecutionResult)
    assert result.status == SUCCEEDED
    assert result.output == {"results": [1, 2, 3]}
    assert result.error is None
    assert result.execution_id is not None

    record = env["execution_records"].get(result.execution_id)
    assert record.status == RECORD_SUCCEEDED


def test_invalid_input_never_executes():
    env = _build()
    _register(env)

    result = env["lifecycle"].execute("agent-1", "web-search", "scope-1", {"query": 123})

    assert result.status == REJECTED_INVALID_INPUT
    assert result.execution_id is None
    assert env["calls"] == []
    assert env["execution_records"].list_for_agent("agent-1") == []


def test_policy_denial_never_executes():
    env = _build()
    env["registry"].register(
        LLMAgentCapability(capability_id="web-search", name="w", description="d", category="retrieval")
    )
    env["contracts"].register(
        LLMAgentCapabilityContract(
            capability_id="web-search", version="1.0.0", input_schema=_INPUT_SCHEMA, output_schema=_OUTPUT_SCHEMA,
        )
    )
    env["policy_service"].create(
        "scope-1", "deny-it", [{"rule_id": "deny-it", "effect": DENY, "match": {"capability_id": "web-search"}}]
    )

    result = env["lifecycle"].execute("agent-1", "web-search", "scope-1", {"query": "x"})

    assert result.status == REJECTED_POLICY_DENIED
    assert result.execution_id is None
    assert env["calls"] == []
    assert env["execution_records"].list_for_agent("agent-1") == []


def test_capability_failure_records_failure_correctly():
    def failing_executor(capability_id, input_payload, context):
        raise RuntimeError("capability blew up")

    env = _build(executor=failing_executor)
    _register(env)

    result = env["lifecycle"].execute("agent-1", "web-search", "scope-1", {"query": "x"})

    assert result.status == FAILED
    assert result.execution_id is not None
    assert "capability blew up" in result.error

    record = env["execution_records"].get(result.execution_id)
    assert record.status == RECORD_FAILED
    assert "capability blew up" in record.error


def test_invalid_output_does_not_produce_a_successful_execution():
    def bad_output_executor(capability_id, input_payload, context):
        return {"results": "not-a-list"}

    env = _build(executor=bad_output_executor)
    _register(env)

    result = env["lifecycle"].execute("agent-1", "web-search", "scope-1", {"query": "x"})

    assert result.status == REJECTED_INVALID_OUTPUT
    assert result.output is None
    assert result.execution_id is not None

    record = env["execution_records"].get(result.execution_id)
    assert record.status == RECORD_FAILED


def test_exact_capability_version_is_preserved():
    env = _build()
    _register(env, version="2.3.1")

    result = env["lifecycle"].execute("agent-1", "web-search", "scope-1", {"query": "x"})

    record = env["execution_records"].get(result.execution_id)
    assert record.capability_version == "2.3.1"


def test_existing_execution_mechanism_is_actually_invoked():
    env = _build()
    _register(env)

    env["lifecycle"].execute("agent-1", "web-search", "scope-1", {"query": "x"}, context={"role": "admin"})

    assert len(env["calls"]) == 1
    capability_id, input_payload, context = env["calls"][0]
    assert capability_id == "web-search"
    assert input_payload == {"query": "x"}
    assert context == {"role": "admin"}


def test_unknown_capability_rejected_without_touching_anything():
    env = _build()

    result = env["lifecycle"].execute("agent-1", "nonexistent", "scope-1", {"query": "x"})

    assert result.status == REJECTED_UNKNOWN_CAPABILITY
    assert result.execution_id is None
    assert result.validation is None
    assert result.policy_decision is None
    assert env["calls"] == []


def test_validation_errors():
    env = _build()
    _register(env)

    with pytest.raises(InvalidCapabilityExecutionLifecycleError):
        env["lifecycle"].execute("", "web-search", "scope-1", {})
    with pytest.raises(InvalidCapabilityExecutionLifecycleError):
        env["lifecycle"].execute("agent-1", "", "scope-1", {})
    with pytest.raises(InvalidCapabilityExecutionLifecycleError):
        env["lifecycle"].execute("agent-1", "web-search", "", {})
    with pytest.raises(InvalidCapabilityExecutionLifecycleError):
        env["lifecycle"].execute("agent-1", "web-search", "scope-1", {}, context="not-a-dict")
