import json

import pytest

from backend.agent_task_planning import (
    LLMAgentPlanningService,
    MalformedAgentPlanResponseError,
    UnknownAgentPlanError,
)
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.llm.tools import LLMToolRegistryService


class ScriptedProvider(LLMProvider):
    """A real LLMProvider that replays one scripted outcome per call, in order."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request):
        raise NotImplementedError


def make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


def build_services(script):
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True)
    )

    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )

    context_service = LLMContextService()
    provider = ScriptedProvider(script)
    orchestration_service = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={"openai": provider},
    )

    registry = LLMToolRegistryService()
    registry.register(
        "search_prerequisites",
        "Search the concept graph for prerequisites of a topic.",
        {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]},
    )
    registry.register(
        "summarize_notes",
        "Summarize a set of study notes.",
        {"type": "object", "properties": {"notes": {"type": "string"}}, "required": ["notes"]},
    )
    registry.register(
        "disabled_tool",
        "A tool that exists but is turned off.",
        {"type": "object", "properties": {}},
        enabled=False,
    )

    planning_service = LLMAgentPlanningService(registry, orchestration_service, context_service)
    return registry, planning_service, provider


SIMPLE_PLAN_RESPONSE = json.dumps(
    {
        "steps": [
            {
                "action": "Find prerequisites for linear algebra",
                "tool": "search_prerequisites",
                "arguments": {"topic": "linear algebra"},
                "depends_on": [],
            }
        ]
    }
)

MULTI_STEP_PLAN_RESPONSE = json.dumps(
    {
        "steps": [
            {
                "action": "Find prerequisites for linear algebra",
                "tool": "search_prerequisites",
                "arguments": {"topic": "linear algebra"},
                "depends_on": [],
            },
            {
                "action": "Summarize the resulting notes",
                "tool": "summarize_notes",
                "arguments": {"notes": "placeholder"},
                "depends_on": [0],
            },
        ]
    }
)


def test_simple_task_plan():
    registry, planning_service, provider = build_services([make_response(SIMPLE_PLAN_RESPONSE)])

    plan = planning_service.create("Learn linear algebra")

    assert plan.task == "Learn linear algebra"
    assert plan.status == "READY"
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.tool_name == "search_prerequisites"
    assert step.arguments == {"topic": "linear algebra"}
    assert step.depends_on == []
    assert step.status == "READY"
    assert planning_service.validate(plan.plan_id) is True


def test_multi_step_plan_with_dependency():
    registry, planning_service, provider = build_services([make_response(MULTI_STEP_PLAN_RESPONSE)])

    plan = planning_service.create("Learn and summarize linear algebra", context={"level": "beginner"})

    assert plan.status == "READY"
    assert len(plan.steps) == 2
    first, second = plan.steps
    assert first.depends_on == []
    assert second.depends_on == [first.step_id]
    assert second.tool_name == "summarize_notes"
    assert provider.calls == 1


def test_invalid_tool_is_rejected():
    response = json.dumps(
        {
            "steps": [
                {
                    "action": "Do something with a tool that does not exist",
                    "tool": "no_such_tool",
                    "arguments": {},
                    "depends_on": [],
                }
            ]
        }
    )
    registry, planning_service, provider = build_services([make_response(response)])

    plan = planning_service.create("Do something unsupported")

    assert plan.status == "REJECTED"
    assert plan.steps[0].status == "REJECTED"
    assert "no_such_tool" in plan.steps[0].errors[0]
    assert planning_service.validate(plan.plan_id) is False


def test_disabled_tool_is_rejected():
    response = json.dumps(
        {
            "steps": [
                {
                    "action": "Use a disabled tool",
                    "tool": "disabled_tool",
                    "arguments": {},
                    "depends_on": [],
                }
            ]
        }
    )
    registry, planning_service, provider = build_services([make_response(response)])

    plan = planning_service.create("Use a disabled capability")

    assert plan.status == "REJECTED"
    assert "disabled" in plan.steps[0].errors[0]


@pytest.mark.parametrize(
    "depends_on",
    [
        [5],
        [0],
    ],
)
def test_dependency_validation_rejects_bad_references(depends_on):
    """[5] is out of range; [0] on the (only) step at index 0 is self-reference."""
    response = json.dumps(
        {
            "steps": [
                {
                    "action": "A step that depends on something invalid",
                    "tool": "search_prerequisites",
                    "arguments": {"topic": "x"},
                    "depends_on": depends_on,
                }
            ]
        }
    )
    registry, planning_service, provider = build_services([make_response(response)])

    plan = planning_service.create("A task with a bad dependency")

    assert plan.status == "REJECTED"
    assert any("invalid step index" in error for error in plan.steps[0].errors)


def test_dependency_validation_rejects_circular_dependency():
    response = json.dumps(
        {
            "steps": [
                {
                    "action": "Step A",
                    "tool": "search_prerequisites",
                    "arguments": {"topic": "x"},
                    "depends_on": [1],
                },
                {
                    "action": "Step B",
                    "tool": "summarize_notes",
                    "arguments": {"notes": "x"},
                    "depends_on": [0],
                },
            ]
        }
    )
    registry, planning_service, provider = build_services([make_response(response)])

    plan = planning_service.create("A task with circular dependencies")

    assert plan.status == "REJECTED"
    assert all(step.status == "REJECTED" for step in plan.steps)
    assert all(
        any("circular" in error for error in step.errors) for step in plan.steps
    )


@pytest.mark.parametrize(
    "malformed_response",
    [
        "not json",
        json.dumps({"steps": []}),
        json.dumps({"steps": "not-a-list"}),
        json.dumps({"steps": [{"tool": "search_prerequisites"}]}),
        json.dumps({"steps": [{"action": "x", "tool": ""}]}),
        json.dumps({"steps": [{"action": "x", "tool": "search_prerequisites", "arguments": "nope"}]}),
        json.dumps({"steps": [{"action": "x", "tool": "search_prerequisites", "depends_on": "nope"}]}),
        json.dumps({"steps": [{"action": "x", "tool": "search_prerequisites", "depends_on": ["0"]}]}),
    ],
)
def test_malformed_llm_response_raises(malformed_response):
    registry, planning_service, provider = build_services([make_response(malformed_response)])

    with pytest.raises(MalformedAgentPlanResponseError):
        planning_service.create("A task with a malformed response")


def test_preview():
    registry, planning_service, provider = build_services([make_response(MULTI_STEP_PLAN_RESPONSE)])
    plan = planning_service.create("Learn and summarize linear algebra")

    preview = planning_service.preview(plan.plan_id)

    assert preview == [
        "step-1: Find prerequisites for linear algebra via search_prerequisites",
        "step-2: Summarize the resulting notes via summarize_notes after step-1",
    ]


def test_preview_shows_rejection_reason():
    response = json.dumps(
        {
            "steps": [
                {"action": "Do it", "tool": "no_such_tool", "arguments": {}, "depends_on": []}
            ]
        }
    )
    registry, planning_service, provider = build_services([make_response(response)])
    plan = planning_service.create("An unsupported task")

    preview = planning_service.preview(plan.plan_id)

    assert len(preview) == 1
    assert preview[0].startswith("REJECTED step-1")
    assert "no_such_tool" in preview[0]


def test_preview_and_validate_unknown_plan_raise():
    registry, planning_service, provider = build_services([make_response(SIMPLE_PLAN_RESPONSE)])

    with pytest.raises(UnknownAgentPlanError):
        planning_service.preview("no-such-plan")
    with pytest.raises(UnknownAgentPlanError):
        planning_service.validate("no-such-plan")
    with pytest.raises(UnknownAgentPlanError):
        planning_service.get("no-such-plan")


def test_planning_never_executes_a_tool():
    """A tool 'handler' would be a callable a dispatcher invokes; the
    registry here holds only declarative definitions with no such callable,
    so there is nothing create()/validate()/preview() could call even if it
    tried. This asserts the observable contract instead: only the one LLM
    call happens, and the registered tool definitions are left untouched."""
    registry, planning_service, provider = build_services([make_response(MULTI_STEP_PLAN_RESPONSE)])
    before = registry.list()

    plan = planning_service.create("Learn and summarize linear algebra")
    planning_service.validate(plan.plan_id)
    planning_service.preview(plan.plan_id)

    assert provider.calls == 1
    assert registry.list() == before
