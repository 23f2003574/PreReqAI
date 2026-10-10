import dataclasses

import pytest

from backend.llm.tool_validation import (
    ENUM,
    LLMToolValidationService,
    MAXIMUM,
    MINIMUM,
    REQUIRED,
    TYPE,
    UNKNOWN_FIELD,
    ToolArgumentValidationError,
)
from backend.llm.tools import (
    DisabledToolError,
    InvalidToolDefinitionError,
    LLMToolDefinition,
    LLMToolRegistryService,
    UnknownToolError,
)

# As in Commit #1, the tool below describes a real project capability --
# Commit #2's LLMAPICandidateService.analyze(analysis_id) -- rather than
# invented functionality.
DETECT_API_CANDIDATES_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_id": {"type": "string", "description": "A prior notebook analysis id."},
        "min_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "include_private": {"type": "boolean"},
        "sort_by": {"type": "string", "enum": ["confidence", "name"]},
    },
    "required": ["analysis_id"],
}


def _registry_with_tool(enabled=True, schema=None):
    registry = LLMToolRegistryService()
    registry.register(
        "detect_api_candidates",
        "Identify API-worthy functions via LLMAPICandidateService.",
        schema if schema is not None else DETECT_API_CANDIDATES_SCHEMA,
        enabled=enabled,
    )
    return registry


def _service(enabled=True, schema=None):
    return LLMToolValidationService(_registry_with_tool(enabled=enabled, schema=schema))


def test_valid_arguments():
    service = _service()

    assert service.errors("detect_api_candidates", {"analysis_id": "analysis-1"}) == []
    assert service.validate_arguments("detect_api_candidates", {"analysis_id": "analysis-1"}) is True

    full = {
        "analysis_id": "analysis-1",
        "min_confidence": 0.5,
        "include_private": False,
        "sort_by": "confidence",
    }
    assert service.errors("detect_api_candidates", full) == []
    assert service.validate_arguments("detect_api_candidates", full) is True


def test_missing_required_field():
    service = _service()

    errors = service.errors("detect_api_candidates", {"min_confidence": 0.5})

    assert len(errors) == 1
    error = errors[0]
    assert error.tool_name == "detect_api_candidates"
    assert error.field == "analysis_id"
    assert error.rule == REQUIRED
    assert "required" in error.message

    with pytest.raises(ToolArgumentValidationError) as excinfo:
        service.validate_arguments("detect_api_candidates", {"min_confidence": 0.5})
    assert excinfo.value.errors == errors


def test_wrong_type():
    service = _service()

    errors = service.errors("detect_api_candidates", {"analysis_id": 42})

    assert len(errors) == 1
    assert errors[0].field == "analysis_id"
    assert errors[0].rule == TYPE
    assert errors[0].value == "string"

    with pytest.raises(ToolArgumentValidationError):
        service.validate_arguments("detect_api_candidates", {"analysis_id": 42})


def test_wrong_type_bool_is_not_a_number():
    """bool is an int subclass in Python -- a boolean must not satisfy
    "number"/"integer", nor a number satisfy "boolean"."""
    service = _service()

    errors = service.errors(
        "detect_api_candidates",
        {"analysis_id": "analysis-1", "min_confidence": True, "include_private": 1},
    )

    by_field = {error.field: error for error in errors}
    assert by_field["min_confidence"].rule == TYPE
    assert by_field["include_private"].rule == TYPE


def test_unknown_field():
    service = _service()

    errors = service.errors(
        "detect_api_candidates", {"analysis_id": "analysis-1", "shell_command": "rm -rf /"}
    )

    assert len(errors) == 1
    assert errors[0].field == "shell_command"
    assert errors[0].rule == UNKNOWN_FIELD

    with pytest.raises(ToolArgumentValidationError):
        service.validate_arguments(
            "detect_api_candidates", {"analysis_id": "analysis-1", "shell_command": "rm -rf /"}
        )


def test_unknown_field_allowed_when_schema_opts_in():
    schema = dict(DETECT_API_CANDIDATES_SCHEMA, additionalProperties=True)
    service = _service(schema=schema)

    assert service.errors("detect_api_candidates", {"analysis_id": "a-1", "extra": 1}) == []


def test_enum_and_numeric_bounds():
    service = _service()

    errors = service.errors(
        "detect_api_candidates",
        {"analysis_id": "analysis-1", "sort_by": "confidenceX", "min_confidence": 1.5},
    )

    by_rule = {error.rule: error for error in errors}
    assert by_rule[ENUM].field == "sort_by"
    assert by_rule[ENUM].value == ["confidence", "name"]
    assert by_rule[MAXIMUM].field == "min_confidence"
    assert by_rule[MAXIMUM].value == 1.0

    below = service.errors(
        "detect_api_candidates", {"analysis_id": "analysis-1", "min_confidence": -0.5}
    )
    assert [error.rule for error in below] == [MINIMUM]


def test_all_errors_reported_together():
    service = _service()

    errors = service.errors(
        "detect_api_candidates", {"min_confidence": "high", "shell_command": "ls"}
    )

    assert {(error.field, error.rule) for error in errors} == {
        ("analysis_id", REQUIRED),
        ("shell_command", UNKNOWN_FIELD),
        ("min_confidence", TYPE),
    }


def test_non_dict_arguments():
    service = _service()

    errors = service.errors("detect_api_candidates", ["analysis-1"])

    assert len(errors) == 1
    assert errors[0].field is None
    assert errors[0].rule == TYPE


def test_disabled_tool():
    service = _service(enabled=False)

    # A disabled tool's arguments are never even inspected, let alone executed.
    with pytest.raises(DisabledToolError):
        service.errors("detect_api_candidates", {"analysis_id": "analysis-1"})

    with pytest.raises(DisabledToolError):
        service.validate_arguments("detect_api_candidates", {"analysis_id": "analysis-1"})


def test_unknown_tool():
    service = _service()

    with pytest.raises(UnknownToolError):
        service.errors("does_not_exist", {"analysis_id": "analysis-1"})

    with pytest.raises(UnknownToolError):
        service.validate_arguments("does_not_exist", {"analysis_id": "analysis-1"})


def test_validate_definition_accepts_a_registered_tool():
    registry = _registry_with_tool()
    service = LLMToolValidationService(registry)

    assert service.validate_definition(registry.get("detect_api_candidates")) is True


@pytest.mark.parametrize(
    "input_schema",
    [
        # Structural failures -- delegated to the registry's validate_input_schema.
        None,
        {},
        {"type": "array", "properties": {}},
        {"type": "object"},
        {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["missing"]},
        # Per-property failures this service adds on top.
        {"type": "object", "properties": {"a": "not-an-object"}},
        {"type": "object", "properties": {"a": {"description": "no type"}}},
        {"type": "object", "properties": {"a": {"type": "str"}}},
        {"type": "object", "properties": {"a": {"type": "string", "enum": "not-a-list"}}},
    ],
)
def test_malformed_schema_rejected(input_schema):
    service = LLMToolValidationService(LLMToolRegistryService())

    tool = LLMToolDefinition(
        tool_id="tool-1",
        name="malformed",
        description="A tool with a malformed schema.",
        input_schema=input_schema,
    )

    with pytest.raises(InvalidToolDefinitionError):
        service.validate_definition(tool)


def test_malformed_definition_rejected():
    service = LLMToolValidationService(LLMToolRegistryService())
    valid = LLMToolDefinition(
        tool_id="tool-1",
        name="ok",
        description="A valid tool.",
        input_schema={"type": "object", "properties": {"a": {"type": "string"}}},
    )

    assert service.validate_definition(valid) is True

    with pytest.raises(InvalidToolDefinitionError):
        service.validate_definition(dataclasses.replace(valid, name=""))

    with pytest.raises(InvalidToolDefinitionError):
        service.validate_definition(dataclasses.replace(valid, description=""))

    with pytest.raises(InvalidToolDefinitionError):
        service.validate_definition({"name": "not-a-definition"})


def test_malformed_schema_blocks_argument_validation():
    """A tool whose stored schema is unusable must fail loudly rather than
    letting arguments through unchecked."""
    registry = LLMToolRegistryService()
    tool = registry.register(
        "detect_api_candidates", "Identify API-worthy functions.", DETECT_API_CANDIDATES_SCHEMA
    )
    # Simulate a definition that went bad after registration.
    registry._tools[tool.tool_id] = dataclasses.replace(
        tool, input_schema={"type": "object", "properties": {"analysis_id": {"type": "str"}}}
    )
    service = LLMToolValidationService(registry)

    with pytest.raises(InvalidToolDefinitionError):
        service.errors("detect_api_candidates", {"analysis_id": "analysis-1"})

    with pytest.raises(InvalidToolDefinitionError):
        service.validate_arguments("detect_api_candidates", {"analysis_id": "analysis-1"})


def test_validation_does_not_execute_tools():
    """The service inspects definitions and argument dicts only -- it has no
    dispatch surface and never calls the capability a tool describes."""
    service = _service()

    for attr in ("invoke", "call", "execute", "run", "dispatch"):
        assert not hasattr(service, attr)


def test_validation_reuses_the_registry_rather_than_copying_state():
    """Enabling/disabling through the registry is reflected immediately --
    this service holds no snapshot of its own."""
    registry = _registry_with_tool(enabled=True)
    service = LLMToolValidationService(registry)

    assert service.validate_arguments("detect_api_candidates", {"analysis_id": "a-1"}) is True

    registry.disable("detect_api_candidates")
    with pytest.raises(DisabledToolError):
        service.validate_arguments("detect_api_candidates", {"analysis_id": "a-1"})

    registry.enable("detect_api_candidates")
    assert service.validate_arguments("detect_api_candidates", {"analysis_id": "a-1"}) is True

    # A tool registered after this service was constructed is visible too.
    registry.register(
        "analyze_notebook",
        "Analyze a notebook via LLMNotebookAnalysisService.",
        {"type": "object", "properties": {"notebook": {"type": "object"}}, "required": ["notebook"]},
    )
    assert service.validate_arguments("analyze_notebook", {"notebook": {}}) is True
