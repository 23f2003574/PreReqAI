import json
from datetime import datetime, timezone

from backend.agent_plan_validation import (
    DEPENDENCY_CYCLE,
    DISABLED_TOOL,
    INVALID_DEPENDENCY,
    PERMISSION_CONFLICT,
    UNKNOWN_TOOL,
    LLMAgentPlanValidationService,
)
from backend.agent_task_planning import LLMAgentPlan, LLMAgentPlanStep, LLMAgentPlanningService
from backend.agent_task_planning import READY as PLAN_READY
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.llm.tool_permissions import ANY_SUBJECT, LLMToolPermissionPolicy, LLMToolPermissionService
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


class FixedPlanStore:
    """A minimal stand-in for LLMAgentPlanningService exposing only get().

    Used to feed the validation service a plan whose shape Commit #1's own
    create() would never itself produce (an unresolved or cyclic
    dependency survives create() only inside a REJECTED step's error text,
    never as a live depends_on reference) -- so validate_dependencies()'s
    own independent graph check can be exercised directly.
    """

    def __init__(self, plan: LLMAgentPlan):
        self._plan = plan

    def get(self, plan_id: str) -> LLMAgentPlan:
        if plan_id != self._plan.plan_id:
            raise KeyError(plan_id)
        return self._plan


def build_services(script, register_disabled=True):
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
    if register_disabled:
        registry.register(
            "disabled_tool",
            "A tool that exists but is turned off.",
            {"type": "object", "properties": {}},
            enabled=False,
        )

    planning_service = LLMAgentPlanningService(registry, orchestration_service, context_service)
    permission_service = LLMToolPermissionService(registry)
    validation_service = LLMAgentPlanValidationService(planning_service, registry, permission_service)
    return registry, planning_service, permission_service, validation_service, provider


def allow_any_subject(permission_service, *tool_names):
    for index, tool_name in enumerate(tool_names):
        permission_service.register(
            LLMToolPermissionPolicy(
                policy_id=f"allow-{tool_name}-{index}",
                tool_name=tool_name,
                subject=ANY_SUBJECT,
                allowed=True,
            )
        )


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


def _manual_plan(steps) -> LLMAgentPlan:
    return LLMAgentPlan(
        plan_id="manual-plan-1",
        task="a manually constructed plan for validation-layer testing",
        steps=steps,
        status=PLAN_READY,
        created_at=datetime.now(timezone.utc),
    )


def test_valid_plan_has_no_findings():
    registry, planning_service, permission_service, validation_service, provider = build_services(
        [make_response(MULTI_STEP_PLAN_RESPONSE)]
    )
    allow_any_subject(permission_service, "search_prerequisites", "summarize_notes")

    plan = planning_service.create("Learn and summarize linear algebra")

    assert validation_service.validate(plan.plan_id) == []
    assert validation_service.blocking(plan.plan_id) is False


def test_unknown_tool_is_a_blocking_finding():
    response = json.dumps(
        {
            "steps": [
                {
                    "action": "Use a tool that does not exist",
                    "tool": "no_such_tool",
                    "arguments": {},
                    "depends_on": [],
                }
            ]
        }
    )
    registry, planning_service, permission_service, validation_service, provider = build_services(
        [make_response(response)]
    )

    plan = planning_service.create("Do something unsupported")

    findings = validation_service.validate_steps(plan.plan_id)

    assert len(findings) == 1
    assert findings[0].step_id == plan.steps[0].step_id
    assert findings[0].category == UNKNOWN_TOOL
    assert findings[0].blocking is True
    assert validation_service.blocking(plan.plan_id) is True


def test_disabled_tool_is_caught_even_if_disabled_after_planning():
    """A tool still enabled at planning time (so Commit #1's own step.status
    is READY) but disabled before validation must still be flagged --
    validation re-checks the live registry rather than trusting the plan's
    own stale status."""
    registry, planning_service, permission_service, validation_service, provider = build_services(
        [make_response(SIMPLE_PLAN_RESPONSE)], register_disabled=False
    )

    plan = planning_service.create("Learn linear algebra")
    assert plan.steps[0].status == "READY"

    registry.disable("search_prerequisites")

    findings = validation_service.validate_steps(plan.plan_id)

    assert len(findings) == 1
    assert findings[0].category == DISABLED_TOOL
    assert findings[0].blocking is True
    assert validation_service.blocking(plan.plan_id) is True


def test_invalid_dependency_reference():
    steps = [
        LLMAgentPlanStep(
            step_id="step-1",
            action="Depend on a step that doesn't exist",
            tool_name="search_prerequisites",
            arguments={"topic": "x"},
            depends_on=["step-99"],
            status="READY",
            errors=[],
        )
    ]
    registry, _, _, _, _ = build_services([])
    validation_service = LLMAgentPlanValidationService(FixedPlanStore(_manual_plan(steps)), registry)

    findings = validation_service.validate_dependencies("manual-plan-1")

    assert len(findings) == 1
    assert findings[0].step_id == "step-1"
    assert findings[0].category == INVALID_DEPENDENCY
    assert findings[0].blocking is True


def test_dependency_cycle_is_rejected():
    steps = [
        LLMAgentPlanStep(
            step_id="step-1",
            action="A",
            tool_name="search_prerequisites",
            arguments={},
            depends_on=["step-2"],
            status="READY",
            errors=[],
        ),
        LLMAgentPlanStep(
            step_id="step-2",
            action="B",
            tool_name="summarize_notes",
            arguments={},
            depends_on=["step-1"],
            status="READY",
            errors=[],
        ),
    ]
    registry, _, _, _, _ = build_services([])
    validation_service = LLMAgentPlanValidationService(FixedPlanStore(_manual_plan(steps)), registry)

    findings = validation_service.validate_dependencies("manual-plan-1")

    assert len(findings) == 2
    assert {finding.step_id for finding in findings} == {"step-1", "step-2"}
    assert all(finding.category == DEPENDENCY_CYCLE for finding in findings)
    assert all(finding.blocking for finding in findings)


def test_permission_conflict_blocks_an_otherwise_valid_plan():
    registry, planning_service, permission_service, validation_service, provider = build_services(
        [make_response(SIMPLE_PLAN_RESPONSE)]
    )
    permission_service.register(
        LLMToolPermissionPolicy(
            policy_id="deny-search",
            tool_name="search_prerequisites",
            subject=ANY_SUBJECT,
            allowed=False,
        )
    )

    plan = planning_service.create("Learn linear algebra")

    findings = validation_service.validate(plan.plan_id)

    assert len(findings) == 1
    assert findings[0].step_id == plan.steps[0].step_id
    assert findings[0].category == PERMISSION_CONFLICT
    assert findings[0].blocking is True
    assert validation_service.blocking(plan.plan_id) is True


def test_multiple_blocking_findings_are_all_reported():
    response = json.dumps(
        {
            "steps": [
                {
                    "action": "Use an unknown tool",
                    "tool": "no_such_tool",
                    "arguments": {},
                    "depends_on": [],
                },
                {
                    "action": "Use a tool nobody may invoke",
                    "tool": "summarize_notes",
                    "arguments": {"notes": "x"},
                    "depends_on": [],
                },
            ]
        }
    )
    registry, planning_service, permission_service, validation_service, provider = build_services(
        [make_response(response)]
    )
    permission_service.register(
        LLMToolPermissionPolicy(
            policy_id="deny-summarize",
            tool_name="summarize_notes",
            subject=ANY_SUBJECT,
            allowed=False,
        )
    )

    plan = planning_service.create("A task with two separate problems")

    findings = validation_service.validate(plan.plan_id)
    categories = {finding.category for finding in findings}

    assert len(findings) == 2
    assert categories == {UNKNOWN_TOOL, PERMISSION_CONFLICT}
    assert all(finding.blocking for finding in findings)
    assert validation_service.blocking(plan.plan_id) is True


def test_validation_never_executes_a_tool():
    registry, planning_service, permission_service, validation_service, provider = build_services(
        [make_response(MULTI_STEP_PLAN_RESPONSE)]
    )
    allow_any_subject(permission_service, "search_prerequisites", "summarize_notes")
    before = registry.list()

    plan = planning_service.create("Learn and summarize linear algebra")
    validation_service.validate(plan.plan_id)
    validation_service.validate_steps(plan.plan_id)
    validation_service.validate_dependencies(plan.plan_id)
    validation_service.blocking(plan.plan_id)

    assert provider.calls == 1
    assert registry.list() == before
