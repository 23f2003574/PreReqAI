import pytest

from backend.agent_capability_contracts import (
    ENUM,
    MAXIMUM,
    MINIMUM,
    MISSING_CONTEXT,
    REQUIRED,
    REQUIREMENT_NOT_MET,
    TYPE,
    DuplicateContractError,
    InvalidCapabilityContractError,
    JsonContractStore,
    LLMAgentCapabilityContract,
    LLMAgentCapabilityContractService,
    UnknownContractError,
)
from backend.agent_capability_registry import LLMAgentCapability, LLMAgentCapabilityRegistry, UnknownCapabilityError

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 10}},
    "required": ["query"],
}
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array"}, "status": {"type": "string", "enum": ["ok", "error"]}},
    "required": ["results", "status"],
}


def _registry_with_capability(capability_id="web-search", version="1.0.0"):
    registry = LLMAgentCapabilityRegistry()
    registry.register(
        LLMAgentCapability(
            capability_id=capability_id,
            name="Web Search",
            description="Search the public web",
            category="retrieval",
            version=version,
        )
    )
    return registry


def _contract(**overrides):
    fields = {
        "capability_id": "web-search",
        "version": "1.0.0",
        "input_schema": _INPUT_SCHEMA,
        "output_schema": _OUTPUT_SCHEMA,
        "required_context": ["user_id"],
        "requirements": {"role": ["admin", "operator"]},
    }
    fields.update(overrides)
    return LLMAgentCapabilityContract(**fields)


def test_register_and_get():
    registry = _registry_with_capability()
    service = LLMAgentCapabilityContractService(registry)

    registered = service.register(_contract())

    assert isinstance(registered, LLMAgentCapabilityContract)
    assert registered.contract_id is not None
    assert registered.created_at is not None

    fetched = service.get("web-search")
    assert fetched.version == "1.0.0"
    assert fetched.input_schema == _INPUT_SCHEMA

    fetched_by_version = service.get("web-search", version="1.0.0")
    assert fetched_by_version.contract_id == registered.contract_id


def test_register_accepts_dict():
    registry = _registry_with_capability()
    service = LLMAgentCapabilityContractService(registry)

    registered = service.register(
        {
            "capability_id": "web-search",
            "version": "1.0.0",
            "input_schema": _INPUT_SCHEMA,
            "output_schema": _OUTPUT_SCHEMA,
        }
    )
    assert registered.capability_id == "web-search"


def test_reject_unknown_capability():
    registry = LLMAgentCapabilityRegistry()
    service = LLMAgentCapabilityContractService(registry)

    with pytest.raises(UnknownCapabilityError):
        service.register(_contract())


def test_get_unknown_capability_or_contract():
    registry = _registry_with_capability()
    service = LLMAgentCapabilityContractService(registry)

    with pytest.raises(UnknownCapabilityError):
        service.get("missing-capability")

    # capability exists but no contract registered yet
    with pytest.raises(UnknownContractError):
        service.get("web-search")
    with pytest.raises(UnknownContractError):
        service.get("web-search", version="9.9.9")


def test_duplicate_contract_rejected():
    registry = _registry_with_capability()
    service = LLMAgentCapabilityContractService(registry)
    service.register(_contract())

    with pytest.raises(DuplicateContractError):
        service.register(_contract())


def test_contract_field_validation():
    registry = _registry_with_capability()
    service = LLMAgentCapabilityContractService(registry)

    with pytest.raises(InvalidCapabilityContractError):
        service.register(_contract(capability_id=""))
    with pytest.raises(InvalidCapabilityContractError):
        service.register(_contract(version=""))
    with pytest.raises(InvalidCapabilityContractError):
        service.register(_contract(input_schema="not-a-schema"))
    with pytest.raises(InvalidCapabilityContractError):
        service.register(_contract(input_schema={"type": "array", "properties": {}}))
    with pytest.raises(InvalidCapabilityContractError):
        service.register(_contract(output_schema={"type": "object"}))  # missing properties
    with pytest.raises(InvalidCapabilityContractError):
        service.register(_contract(required_context=["", "ok"]))
    with pytest.raises(InvalidCapabilityContractError):
        service.register(_contract(requirements={"": "x"}))
    with pytest.raises(InvalidCapabilityContractError):
        service.register(_contract(metadata="not-a-dict"))
    with pytest.raises(InvalidCapabilityContractError):
        service.register("not-a-contract-or-dict")


def test_validate_input_valid_and_invalid_payloads():
    registry = _registry_with_capability()
    service = LLMAgentCapabilityContractService(registry)
    service.register(_contract())

    valid = service.validate_input("web-search", {"query": "transformers", "limit": 5})
    assert valid.valid is True
    assert valid.violations == []

    missing_required = service.validate_input("web-search", {"limit": 5})
    assert missing_required.valid is False
    assert any(v.rule == REQUIRED and v.field == "query" for v in missing_required.violations)

    wrong_type = service.validate_input("web-search", {"query": 123})
    assert wrong_type.valid is False
    assert any(v.rule == TYPE and v.field == "query" for v in wrong_type.violations)

    out_of_range = service.validate_input("web-search", {"query": "x", "limit": 99})
    assert out_of_range.valid is False
    assert any(v.rule == MAXIMUM and v.field == "limit" for v in out_of_range.violations)

    unknown_field = service.validate_input("web-search", {"query": "x", "extra": 1})
    assert unknown_field.valid is False
    assert any(v.field == "extra" for v in unknown_field.violations)

    not_an_object = service.validate_input("web-search", "not-a-dict")
    assert not_an_object.valid is False
    assert not_an_object.violations[0].rule == TYPE


def test_validate_output_valid_and_invalid_payloads():
    registry = _registry_with_capability()
    service = LLMAgentCapabilityContractService(registry)
    service.register(_contract())

    valid = service.validate_output("web-search", {"results": [1, 2], "status": "ok"})
    assert valid.valid is True

    bad_enum = service.validate_output("web-search", {"results": [], "status": "weird"})
    assert bad_enum.valid is False
    assert any(v.rule == ENUM and v.field == "status" for v in bad_enum.violations)

    missing = service.validate_output("web-search", {"status": "ok"})
    assert missing.valid is False
    assert any(v.rule == REQUIRED and v.field == "results" for v in missing.violations)


def test_check_requirements_reports_missing_context_and_requirements():
    registry = _registry_with_capability()
    service = LLMAgentCapabilityContractService(registry)
    service.register(_contract())

    satisfied = service.check_requirements("web-search", {"user_id": "u1", "role": "admin"})
    assert satisfied.valid is True
    assert satisfied.violations == []

    missing_context = service.check_requirements("web-search", {"role": "admin"})
    assert missing_context.valid is False
    assert any(v.rule == MISSING_CONTEXT and v.field == "user_id" for v in missing_context.violations)

    unmet_requirement = service.check_requirements("web-search", {"user_id": "u1", "role": "guest"})
    assert unmet_requirement.valid is False
    assert any(v.rule == REQUIREMENT_NOT_MET and v.field == "role" for v in unmet_requirement.violations)

    both_missing = service.check_requirements("web-search", {})
    assert both_missing.valid is False
    rules = {(v.field, v.rule) for v in both_missing.violations}
    assert ("user_id", MISSING_CONTEXT) in rules
    assert ("role", REQUIREMENT_NOT_MET) in rules

    with pytest.raises(InvalidCapabilityContractError):
        service.check_requirements("web-search", "not-a-dict")


def test_version_specific_contracts_resolve_correctly():
    registry = _registry_with_capability(version="1.0.0")
    service = LLMAgentCapabilityContractService(registry)
    service.register(_contract(version="1.0.0", requirements={}))
    service.register(_contract(version="2.0.0", requirements={"role": "admin"}))

    # version=None resolves against the capability's current registry version
    current = service.get("web-search")
    assert current.version == "1.0.0"

    v2 = service.get("web-search", version="2.0.0")
    assert v2.version == "2.0.0"
    assert v2.requirements == {"role": "admin"}

    # advancing the capability's own version changes what version=None resolves to
    registry.update("web-search", {"version": "2.0.0"})
    assert service.get("web-search").version == "2.0.0"

    # the old version's contract is untouched and still directly reachable
    assert service.get("web-search", version="1.0.0").requirements == {}


def test_contract_changes_do_not_invalidate_existing_versions():
    registry = _registry_with_capability(version="1.0.0")
    service = LLMAgentCapabilityContractService(registry)
    original = service.register(_contract(version="1.0.0"))

    registry.update("web-search", {"version": "2.0.0"})
    service.register(_contract(version="2.0.0", input_schema={"type": "object", "properties": {}, "required": []}))

    # the original, still-registered version's contract is byte-for-byte unchanged
    still_there = service.get("web-search", version="1.0.0")
    assert still_there.contract_id == original.contract_id
    assert still_there.input_schema == _INPUT_SCHEMA


def test_validation_is_side_effect_free():
    registry = _registry_with_capability()
    service = LLMAgentCapabilityContractService(registry)
    contract = service.register(_contract())

    service.validate_input("web-search", {"query": "x"})
    service.validate_output("web-search", {"status": "bad-enum-value", "results": []})
    service.check_requirements("web-search", {})

    assert service.get("web-search") == contract
    assert registry.get("web-search").status == "active"


def test_json_store_round_trip(tmp_path):
    path = tmp_path / "contracts.json"
    registry = _registry_with_capability()

    service1 = LLMAgentCapabilityContractService(registry, store=JsonContractStore(path))
    service1.register(_contract())

    service2 = LLMAgentCapabilityContractService(registry, store=JsonContractStore(path))
    fetched = service2.get("web-search")
    assert fetched.input_schema == _INPUT_SCHEMA
    assert fetched.required_context == ["user_id"]
