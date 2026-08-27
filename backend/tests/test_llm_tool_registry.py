import pytest

from backend.llm.tools import (
    DisabledToolError,
    DuplicateToolNameError,
    InvalidToolDefinitionError,
    LLMToolRegistryService,
    UnknownToolError,
)

# Input schemas below describe real project capabilities (Commit #1's
# LLMNotebookAnalysisService.analyze, Commit #2's LLMAPICandidateService.analyze,
# and Commit #11's LLMCodePatchPlanningService.plan) -- this registry does not
# invent tools for functionality that doesn't exist in the repo.

ANALYZE_NOTEBOOK_SCHEMA = {
    "type": "object",
    "properties": {
        "notebook": {"type": "object", "description": "The notebook document to analyze."},
    },
    "required": ["notebook"],
}

DETECT_API_CANDIDATES_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_id": {"type": "string", "description": "A prior notebook analysis id."},
    },
    "required": ["analysis_id"],
}

PLAN_CODE_PATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestion_id": {"type": "string", "description": "A code fix suggestion id."},
    },
    "required": ["suggestion_id"],
}


def test_register_and_get():
    service = LLMToolRegistryService()

    tool = service.register(
        "analyze_notebook",
        "Analyze a notebook's structure via LLMNotebookAnalysisService.",
        ANALYZE_NOTEBOOK_SCHEMA,
    )

    assert tool.tool_id == "tool-1"
    assert tool.name == "analyze_notebook"
    assert tool.input_schema == ANALYZE_NOTEBOOK_SCHEMA
    assert tool.enabled is True

    fetched = service.get("analyze_notebook")
    assert fetched == tool


def test_duplicate_name_rejected():
    service = LLMToolRegistryService()
    service.register("analyze_notebook", "Analyze a notebook.", ANALYZE_NOTEBOOK_SCHEMA)

    with pytest.raises(DuplicateToolNameError):
        service.register("analyze_notebook", "A different description.", ANALYZE_NOTEBOOK_SCHEMA)


@pytest.mark.parametrize(
    "name,description,input_schema",
    [
        ("", "A description.", ANALYZE_NOTEBOOK_SCHEMA),
        ("no_description", "", ANALYZE_NOTEBOOK_SCHEMA),
        ("no_schema", "A description.", None),
        ("not_a_dict_schema", "A description.", "not-a-schema"),
        ("empty_schema", "A description.", {}),
        ("missing_type", "A description.", {"properties": {}}),
        ("wrong_type", "A description.", {"type": "array", "properties": {}}),
        ("missing_properties", "A description.", {"type": "object"}),
        (
            "bad_required",
            "A description.",
            {"type": "object", "properties": {"a": {"type": "string"}}, "required": "a"},
        ),
        (
            "unknown_required_field",
            "A description.",
            {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["missing"]},
        ),
    ],
)
def test_schema_validation_rejects_malformed_definitions(name, description, input_schema):
    service = LLMToolRegistryService()

    with pytest.raises(InvalidToolDefinitionError):
        service.register(name, description, input_schema)

    assert service.list() == []


def test_enable_disable():
    service = LLMToolRegistryService()
    service.register(
        "detect_api_candidates",
        "Identify API-worthy functions via LLMAPICandidateService.",
        DETECT_API_CANDIDATES_SCHEMA,
        enabled=False,
    )

    assert service.get("detect_api_candidates").enabled is False

    enabled_tool = service.enable("detect_api_candidates")
    assert enabled_tool.enabled is True
    assert service.get("detect_api_candidates").enabled is True

    disabled_tool = service.disable("detect_api_candidates")
    assert disabled_tool.enabled is False
    assert service.get("detect_api_candidates").enabled is False

    with pytest.raises(UnknownToolError):
        service.enable("does-not-exist")

    with pytest.raises(UnknownToolError):
        service.disable("does-not-exist")


def test_disabled_lookup_cannot_be_invoked():
    service = LLMToolRegistryService()
    service.register(
        "plan_code_patch",
        "Plan a code patch via LLMCodePatchPlanningService.",
        PLAN_CODE_PATCH_SCHEMA,
        enabled=False,
    )

    # get() still returns a disabled tool for introspection/listing purposes...
    assert service.get("plan_code_patch").enabled is False

    # ...but get_invocable(), the entry point future dispatch code would use,
    # refuses to hand back a disabled tool.
    with pytest.raises(DisabledToolError):
        service.get_invocable("plan_code_patch")

    service.enable("plan_code_patch")
    assert service.get_invocable("plan_code_patch").name == "plan_code_patch"


def test_unknown_tool_lookup():
    service = LLMToolRegistryService()

    with pytest.raises(UnknownToolError):
        service.get("does-not-exist")

    with pytest.raises(UnknownToolError):
        service.get_invocable("does-not-exist")


def test_list_all_and_enabled_only():
    service = LLMToolRegistryService()
    service.register("analyze_notebook", "Analyze a notebook.", ANALYZE_NOTEBOOK_SCHEMA, enabled=True)
    service.register(
        "detect_api_candidates",
        "Identify API-worthy functions.",
        DETECT_API_CANDIDATES_SCHEMA,
        enabled=False,
    )

    all_tools = service.list()
    assert {tool.name for tool in all_tools} == {"analyze_notebook", "detect_api_candidates"}

    enabled_only = service.list(enabled_only=True)
    assert [tool.name for tool in enabled_only] == ["analyze_notebook"]


def test_tool_isolation_across_registrations_and_instances():
    service = LLMToolRegistryService()
    analyze = service.register("analyze_notebook", "Analyze a notebook.", ANALYZE_NOTEBOOK_SCHEMA)
    service.register(
        "detect_api_candidates",
        "Identify API-worthy functions.",
        DETECT_API_CANDIDATES_SCHEMA,
    )

    # Disabling one tool must not affect another's state, id, schema, or description.
    service.disable("detect_api_candidates")

    still_enabled = service.get("analyze_notebook")
    assert still_enabled.enabled is True
    assert still_enabled == analyze

    # Mutating the schema dict passed at registration must not silently
    # mutate the stored, already-validated definition.
    mutable_schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": []}
    tool = service.register("mutable_input", "A tool with a caller-owned schema dict.", mutable_schema)
    mutable_schema["properties"]["y"] = {"type": "string"}
    assert "y" not in tool.input_schema["properties"]
    assert "y" not in service.get("mutable_input").input_schema["properties"]

    # A second, independent registry instance shares no state with the first.
    other_service = LLMToolRegistryService()
    with pytest.raises(UnknownToolError):
        other_service.get("analyze_notebook")
    assert other_service.list() == []


def test_registry_does_not_execute_tools():
    """The registry's public surface has no invoke/call/execute method -- it
    only catalogs definitions. Dispatching a real invocation is out of scope
    for this commit."""
    service = LLMToolRegistryService()
    for attr in ("invoke", "call", "execute", "run"):
        assert not hasattr(service, attr)
