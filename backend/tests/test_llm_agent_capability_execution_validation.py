import pytest

from backend.agent_capability_contracts import LLMAgentCapabilityContract, LLMAgentCapabilityContractService
from backend.agent_capability_execution_validation import (
    ExecutionValidationResult,
    InvalidExecutionValidationError,
    LLMAgentCapabilityExecutionValidator,
)
from backend.agent_capability_registry import LLMAgentCapability, LLMAgentCapabilityRegistry

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
}
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array"}},
    "required": ["results"],
}


def _build():
    registry = LLMAgentCapabilityRegistry()
    contracts = LLMAgentCapabilityContractService(registry)
    validator = LLMAgentCapabilityExecutionValidator(contracts)
    return registry, contracts, validator


def _register(registry, contracts, capability_id="web-search", version="1.0.0", **overrides):
    registry.register(
        LLMAgentCapability(
            capability_id=capability_id, name=capability_id, description="d", category="retrieval", version=version,
        )
    )
    fields = {
        "capability_id": capability_id,
        "version": version,
        "input_schema": _INPUT_SCHEMA,
        "output_schema": _OUTPUT_SCHEMA,
        "required_context": ["user_id"],
    }
    fields.update(overrides)
    contracts.register(LLMAgentCapabilityContract(**fields))


def test_valid_input_passes():
    registry, contracts, validator = _build()
    _register(registry, contracts)

    result = validator.validate_start("web-search", "1.0.0", {"query": "x"}, {"user_id": "u1"})

    assert isinstance(result, ExecutionValidationResult)
    assert result.valid is True
    assert result.errors == []


def test_invalid_input_is_rejected():
    registry, contracts, validator = _build()
    _register(registry, contracts)

    result = validator.validate_start("web-search", "1.0.0", {"query": 123}, {"user_id": "u1"})

    assert result.valid is False
    assert any("query" in error for error in result.errors)


def test_missing_required_context_is_detected():
    registry, contracts, validator = _build()
    _register(registry, contracts)

    result = validator.validate_start("web-search", "1.0.0", {"query": "x"}, {})

    assert result.valid is False
    assert any("user_id" in error for error in result.errors)


def test_valid_output_passes():
    registry, contracts, validator = _build()
    _register(registry, contracts)

    result = validator.validate_result("web-search", "1.0.0", {"results": [1, 2]})

    assert result.valid is True
    assert result.errors == []


def test_invalid_output_is_rejected():
    registry, contracts, validator = _build()
    _register(registry, contracts)

    result = validator.validate_result("web-search", "1.0.0", {"results": "not-a-list"})

    assert result.valid is False
    assert any("results" in error for error in result.errors)


def test_version_specific_contracts_are_respected():
    registry, contracts, validator = _build()
    _register(registry, contracts, version="1.0.0", required_context=[])
    contracts.register(
        LLMAgentCapabilityContract(
            capability_id="web-search",
            version="2.0.0",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            output_schema=_OUTPUT_SCHEMA,
            required_context=["user_id"],
        )
    )

    v1_result = validator.validate_start("web-search", "1.0.0", {"query": "x"}, {})
    assert v1_result.valid is True

    v2_result = validator.validate_start("web-search", "2.0.0", {"query": "x"}, {})
    assert v2_result.valid is False
    assert any("user_id" in error for error in v2_result.errors)


def test_unknown_capability_or_version_fails():
    registry, contracts, validator = _build()
    _register(registry, contracts)

    unknown_capability = validator.validate_start("nonexistent", "1.0.0", {}, {})
    assert unknown_capability.valid is False

    unknown_version = validator.validate_start("web-search", "9.9.9", {}, {})
    assert unknown_version.valid is False

    unknown_result_capability = validator.validate_result("nonexistent", "1.0.0", {})
    assert unknown_result_capability.valid is False


def test_security_warning_does_not_block_validity():
    registry, contracts, validator = _build()
    _register(registry, contracts, required_context=[])

    result = validator.validate_start(
        "web-search", "1.0.0", {"query": "sk-abcdefghijklmnop"}, {}
    )

    assert result.valid is True
    assert any("query" in warning for warning in result.warnings)


def test_validation_performs_no_state_mutation():
    registry, contracts, validator = _build()
    _register(registry, contracts)

    before_capability = registry.get("web-search")
    before_contract = contracts.get("web-search")

    validator.validate_start("web-search", "1.0.0", {"query": 123}, {})
    validator.validate_result("web-search", "1.0.0", {"results": "bad"})

    assert registry.get("web-search") == before_capability
    assert contracts.get("web-search") == before_contract


def test_validation_errors():
    _registry, _contracts, validator = _build()

    with pytest.raises(InvalidExecutionValidationError):
        validator.validate_start("", "1.0.0", {}, {})
    with pytest.raises(InvalidExecutionValidationError):
        validator.validate_start("web-search", "", {}, {})
    with pytest.raises(InvalidExecutionValidationError):
        validator.validate_start("web-search", "1.0.0", {}, "not-a-dict")
    with pytest.raises(InvalidExecutionValidationError):
        validator.validate_result("", "1.0.0", {})
    with pytest.raises(InvalidExecutionValidationError):
        validator.validate_result("web-search", "", {})
