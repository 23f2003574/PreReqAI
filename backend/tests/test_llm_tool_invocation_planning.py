import copy
import dataclasses
import json

import pytest

from backend.llm.tool_invocation import (
    DISABLED_TOOL,
    LLMToolInvocationService,
    MALFORMED_SCHEMA,
    MalformedToolCallError,
    READY,
    REJECTED,
    UNKNOWN_TOOL,
    UnknownToolPlanError,
)
from backend.llm.tool_validation import REQUIRED, TYPE, UNKNOWN_FIELD
from backend.llm.tools import LLMToolRegistryService

# As in Commits #1-#2, the tool describes a real project capability --
# LLMAPICandidateService.analyze(analysis_id) -- not invented functionality.
DETECT_API_CANDIDATES_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_id": {"type": "string", "description": "A prior notebook analysis id."},
        "min_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["analysis_id"],
}


def _registry(enabled=True, schema=None):
    registry = LLMToolRegistryService()
    registry.register(
        "detect_api_candidates",
        "Identify API-worthy functions via LLMAPICandidateService.",
        schema if schema is not None else DETECT_API_CANDIDATES_SCHEMA,
        enabled=enabled,
    )
    return registry


def _service(enabled=True, schema=None):
    return LLMToolInvocationService(_registry(enabled=enabled, schema=schema))


def _call(**overrides):
    call = {
        "id": "call-1",
        "name": "detect_api_candidates",
        "arguments": {"analysis_id": "analysis-1"},
    }
    call.update(overrides)
    return call


def test_valid_plan():
    service = _service()

    plan = service.plan(_call(rationale="The notebook was just analyzed."))

    assert plan.plan_id == "tool-plan-detect_api_candidates-1"
    assert plan.tool_name == "detect_api_candidates"
    assert plan.arguments == {"analysis_id": "analysis-1"}
    assert plan.rationale == "The notebook was just analyzed."
    assert plan.status == READY
    assert plan.errors == []

    assert service.validate(plan.plan_id) is True
    assert service.get(plan.plan_id) == plan


def test_original_tool_call_is_preserved_verbatim():
    service = _service()
    original = _call(rationale="Because it was analyzed.", vendor_extra={"index": 0})

    plan = service.plan(copy.deepcopy(original))

    assert plan.tool_call == original


def test_rationale_falls_back_to_the_registered_description():
    """No LLM is consulted for a rationale -- a plan describes the call that
    was actually made."""
    service = _service()

    plan = service.plan(_call())

    assert plan.status == READY
    assert "detect_api_candidates" in plan.rationale
    assert "Identify API-worthy functions" in plan.rationale


def test_argument_validation_rejects_the_plan():
    service = _service()

    missing = service.plan(_call(arguments={"min_confidence": 0.5}))
    assert missing.status == REJECTED
    assert [(e.field, e.rule) for e in missing.errors] == [("analysis_id", REQUIRED)]
    assert service.validate(missing.plan_id) is False

    wrong_type = service.plan(_call(arguments={"analysis_id": 42}))
    assert wrong_type.status == REJECTED
    assert [(e.field, e.rule) for e in wrong_type.errors] == [("analysis_id", TYPE)]

    unknown_field = service.plan(
        _call(arguments={"analysis_id": "analysis-1", "shell_command": "rm -rf /"})
    )
    assert unknown_field.status == REJECTED
    assert [(e.field, e.rule) for e in unknown_field.errors] == [
        ("shell_command", UNKNOWN_FIELD)
    ]

    # Rejected calls are still recorded, exactly as the model produced them.
    assert unknown_field.tool_call["arguments"]["shell_command"] == "rm -rf /"


def test_unknown_tool():
    service = _service()

    plan = service.plan(_call(name="does_not_exist"))

    assert plan.status == REJECTED
    assert plan.tool_name == "does_not_exist"
    assert [(e.field, e.rule) for e in plan.errors] == [(None, UNKNOWN_TOOL)]
    assert service.validate(plan.plan_id) is False


def test_disabled_tool():
    service = _service(enabled=False)

    plan = service.plan(_call())

    assert plan.status == REJECTED
    assert [(e.field, e.rule) for e in plan.errors] == [(None, DISABLED_TOOL)]
    assert service.validate(plan.plan_id) is False


def test_malformed_tool_definition_rejects_the_plan():
    service = _service(
        schema={"type": "object", "properties": {"analysis_id": {"type": "str"}}}
    )

    plan = service.plan(_call())

    assert plan.status == REJECTED
    assert [(e.field, e.rule) for e in plan.errors] == [(None, MALFORMED_SCHEMA)]


@pytest.mark.parametrize(
    "tool_call",
    [
        None,
        42,
        ["detect_api_candidates"],
        {},
        {"arguments": {"analysis_id": "analysis-1"}},
        {"name": ""},
        {"name": 42},
        {"name": "detect_api_candidates", "arguments": ["analysis-1"]},
        "not-json",
    ],
)
def test_malformed_call_is_refused_outright(tool_call):
    """A call with no usable tool name has nothing to plan against, so it is
    refused rather than recorded."""
    service = _service()

    with pytest.raises(MalformedToolCallError):
        service.plan(tool_call)

    assert service.plans() == []


def test_json_string_tool_call_is_accepted():
    """Tool calls often reach a caller as JSON text in LLMResponse.content --
    that form is planned without LLMResponse itself being changed."""
    service = _service()

    plan = service.plan(json.dumps(_call()))

    assert plan.status == READY
    assert plan.arguments == {"analysis_id": "analysis-1"}


def test_json_string_arguments_are_decoded():
    service = _service()

    plan = service.plan(_call(arguments=json.dumps({"analysis_id": "analysis-1"})))

    assert plan.status == READY
    assert plan.arguments == {"analysis_id": "analysis-1"}


def test_undecodable_string_arguments_are_rejected_not_raised():
    service = _service()

    plan = service.plan(_call(arguments="{not json"))

    assert plan.status == REJECTED
    assert plan.errors[0].rule == TYPE


def test_preview():
    service = _service()
    plan = service.plan(_call(rationale="The notebook was just analyzed."))

    lines = service.preview(plan.plan_id)

    assert lines[0] == "CALL detect_api_candidates"
    assert "analysis_id = 'analysis-1'" in lines[1]
    assert lines[-1] == "  -- The notebook was just analyzed."


def test_preview_of_a_rejected_plan_explains_why():
    service = _service()
    plan = service.plan(_call(arguments={}))

    lines = service.preview(plan.plan_id)

    assert lines[0] == "REJECTED detect_api_candidates"
    assert any(REQUIRED in line and "analysis_id" in line for line in lines[1:])


def test_unknown_plan_lookup():
    service = _service()

    for method in (service.validate, service.preview, service.get):
        with pytest.raises(UnknownToolPlanError):
            method("does-not-exist")


def test_validate_rechecks_live_registry_state():
    """validate() re-runs the checks rather than trusting the stored status --
    a tool disabled after planning must fail."""
    registry = _registry()
    service = LLMToolInvocationService(registry)
    plan = service.plan(_call())

    assert service.validate(plan.plan_id) is True

    registry.disable("detect_api_candidates")
    assert service.validate(plan.plan_id) is False
    assert service.get(plan.plan_id).status == READY  # the record itself is unchanged

    registry.enable("detect_api_candidates")
    assert service.validate(plan.plan_id) is True


def test_execution_immutability():
    """Planning executes nothing and mutates nothing -- not the caller's call,
    not the recorded plan, not the registry."""
    registry = _registry()
    service = LLMToolInvocationService(registry)

    call = _call()
    plan = service.plan(call)
    before = dataclasses.asdict(plan)

    # The service has no dispatch surface at all.
    for attr in ("invoke", "call", "execute", "run", "dispatch", "apply"):
        assert not hasattr(service, attr)

    # Mutating the caller's dict afterward cannot reach the recorded plan.
    call["arguments"]["analysis_id"] = "tampered"
    call["name"] = "tampered"
    assert plan.arguments == {"analysis_id": "analysis-1"}
    assert plan.tool_call["arguments"] == {"analysis_id": "analysis-1"}
    assert plan.tool_name == "detect_api_candidates"

    # validate()/preview() are read-only.
    service.validate(plan.plan_id)
    service.preview(plan.plan_id)
    assert dataclasses.asdict(service.get(plan.plan_id)) == before

    # The plan record itself is frozen.
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.status = REJECTED

    # Planning never touched the registry.
    assert [tool.name for tool in registry.list()] == ["detect_api_candidates"]
    assert registry.get("detect_api_candidates").enabled is True


def test_plans_listing_and_status_filter():
    service = _service()
    ready = service.plan(_call())
    rejected = service.plan(_call(arguments={}))

    assert {plan.plan_id for plan in service.plans()} == {ready.plan_id, rejected.plan_id}
    assert [plan.plan_id for plan in service.plans(status=READY)] == [ready.plan_id]
    assert [plan.plan_id for plan in service.plans(status=REJECTED)] == [rejected.plan_id]
