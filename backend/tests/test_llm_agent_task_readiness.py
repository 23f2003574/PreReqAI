import json

import pytest

from backend.agent_policy_engine import DENY, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_lifecycle import (
    COMPLETED,
    CREATED,
    PAUSED,
    PLANNED,
    READY,
    RUNNING,
    LLMAgentTaskLifecycleService,
)
from backend.agent_task_planning import LLMAgentPlanningService
from backend.agent_task_readiness import AgentTaskReadinessResult, LLMAgentTaskReadinessService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.llm.tools import LLMToolRegistryService


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _task_in_state(lifecycle_service, state, **definition_overrides):
    task = lifecycle_service.create(_definition(**definition_overrides))
    for target in (PLANNED, READY, RUNNING, PAUSED):
        if task.current_state == state:
            return task
        if target == RUNNING and state == PAUSED:
            task = lifecycle_service.transition(task.task_id, RUNNING)
            task = lifecycle_service.transition(task.task_id, PAUSED)
            return task
        task = lifecycle_service.transition(task.task_id, target)
        if task.current_state == state:
            return task
    return task


class ScriptedProvider(LLMProvider):
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


def _plan_response(tool_name="search_prerequisites"):
    return json.dumps(
        {
            "steps": [
                {
                    "action": "Find prerequisites for linear algebra",
                    "tool": tool_name,
                    "arguments": {"topic": "linear algebra"},
                    "depends_on": [],
                }
            ]
        }
    )


def _build_planning_service(script):
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
        context_service=context_service, routing_service=routing_service, providers={"openai": provider}
    )
    registry = LLMToolRegistryService()
    registry.register(
        "search_prerequisites",
        "Search the concept graph for prerequisites of a topic.",
        {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]},
    )
    planning_service = LLMAgentPlanningService(registry, orchestration_service, context_service)
    return registry, planning_service


def _make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


# --- fully valid task -> ready -------------------------------------------------------


def test_fully_valid_task_is_ready():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)

    result = readiness_service.check(task.task_id)

    assert isinstance(result, AgentTaskReadinessResult)
    assert result.ready is True
    assert result.blocking_reasons == []
    assert result.task_id == task.task_id
    assert readiness_service.is_ready(task.task_id) is True


def test_paused_task_is_also_ready_to_resume():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, PAUSED)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is True


# --- missing task -----------------------------------------------------------------------


def test_missing_task_is_blocked():
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)

    result = readiness_service.check("does-not-exist")

    assert result.ready is False
    assert any("does not exist" in reason for reason in result.blocking_reasons)
    assert [check.name for check in result.checks] == ["task_exists"]


# --- invalid lifecycle state -> blocked --------------------------------------------------


@pytest.mark.parametrize("state", [CREATED, PLANNED, RUNNING])
def test_lifecycle_state_that_cannot_enter_execution_is_blocked(state):
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, state)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is False
    assert any("lifecycle state" in reason for reason in result.blocking_reasons)


# --- missing required prerequisite -> blocked with reason -----------------------------------


def test_missing_required_context_blocks_with_reason():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY, requires_context=True)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, context_service=LLMAgentTaskContextService())

    result = readiness_service.check(task.task_id)

    assert result.ready is False
    assert any("context" in reason and "not available" in reason for reason in result.blocking_reasons)


def test_present_context_satisfies_the_requirement():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY, requires_context=True)
    context_service = LLMAgentTaskContextService()
    context_service.create(
        agent_id=task.agent_id,
        scope_id=task.scope_id,
        objective=task.objective,
        task_id=task.task_id,
        relevant_context=[{"context_id": "ctx-1", "context_type": "fact", "content": "some fact"}],
    )
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, context_service=context_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is True
    assert result.warnings == []


def test_missing_referenced_plan_blocks_with_reason():
    lifecycle_service = LLMAgentTaskLifecycleService()
    _, planning_service = _build_planning_service([_make_response(_plan_response())])
    task = _task_in_state(lifecycle_service, READY, plan_id="does-not-exist")
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, planning_service=planning_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is False
    assert any("referenced plan" in reason for reason in result.blocking_reasons)


def test_plan_that_fails_revalidation_blocks_with_reason():
    lifecycle_service = LLMAgentTaskLifecycleService()
    registry, planning_service = _build_planning_service([_make_response(_plan_response())])
    plan = planning_service.create("Learn linear algebra")
    registry.disable("search_prerequisites")
    task = _task_in_state(lifecycle_service, READY, plan_id=plan.plan_id)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, planning_service=planning_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is False
    assert any("is not valid" in reason for reason in result.blocking_reasons)


def test_valid_referenced_plan_satisfies_the_requirement():
    lifecycle_service = LLMAgentTaskLifecycleService()
    _, planning_service = _build_planning_service([_make_response(_plan_response())])
    plan = planning_service.create("Learn linear algebra")
    task = _task_in_state(lifecycle_service, READY, plan_id=plan.plan_id)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, planning_service=planning_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is True


def test_plan_check_is_skipped_without_a_configured_planning_service():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY, plan_id="some-plan-that-was-never-checked")
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is True
    assert "plan" not in [check.name for check in result.checks]


def test_unsatisfied_dependency_blocks_with_reason():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY)
    prerequisite = _task_in_state(lifecycle_service, RUNNING)
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_service.add_dependency(task.task_id, prerequisite.task_id)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, dependency_service=dependency_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is False
    assert any("has not completed yet" in reason for reason in result.blocking_reasons)


def test_satisfied_dependency_does_not_block():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY)
    prerequisite = _task_in_state(lifecycle_service, RUNNING)
    prerequisite = lifecycle_service.transition(prerequisite.task_id, COMPLETED)
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_service.add_dependency(task.task_id, prerequisite.task_id)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, dependency_service=dependency_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is True
    assert "dependencies" in [check.name for check in result.checks]


def test_dependency_check_is_skipped_without_a_configured_dependency_service():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is True
    assert "dependencies" not in [check.name for check in result.checks]


def test_policy_deny_blocks_with_reason():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY)

    policy_service = LLMAgentPolicyService()
    policy_service.create(
        scope_id=task.scope_id,
        name="block task execution",
        rules=[
            LLMAgentPolicyRule(
                rule_id="deny-1",
                effect=DENY,
                match={"action": "agent_task_execution"},
                reason="task execution is disabled in this scope",
            )
        ],
    )
    policy_enforcement = LLMAgentPolicyEnforcement(LLMAgentPolicyResolver(policy_service))
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, policy_enforcement=policy_enforcement)

    result = readiness_service.check(task.task_id)

    assert result.ready is False
    assert any("policy denies" in reason for reason in result.blocking_reasons)


def test_no_applicable_policy_does_not_block():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)  # fresh, empty policy store by default

    result = readiness_service.check(task.task_id)

    assert result.ready is True


# --- multiple blockers -> all reported ------------------------------------------------------


def test_multiple_blockers_are_all_reported():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, CREATED, requires_context=True)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, context_service=LLMAgentTaskContextService())

    result = readiness_service.check(task.task_id)

    assert result.ready is False
    assert len(result.blocking_reasons) >= 2
    assert any("lifecycle state" in reason for reason in result.blocking_reasons)
    assert any("context" in reason for reason in result.blocking_reasons)


# --- warnings do not incorrectly block readiness --------------------------------------------


def test_warnings_do_not_block_readiness():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY, requires_context=True)
    context_service = LLMAgentTaskContextService()
    context_service.create(
        agent_id=task.agent_id, scope_id=task.scope_id, objective=task.objective, task_id=task.task_id
    )  # created with no relevant_context entries at all
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service, context_service=context_service)

    result = readiness_service.check(task.task_id)

    assert result.ready is True
    assert result.blocking_reasons == []
    assert any("relevant_context" in warning for warning in result.warnings)


# --- service performs no mutation ------------------------------------------------------------


def test_check_does_not_mutate_the_task():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)

    before = lifecycle_service.get(task.task_id)
    readiness_service.check(task.task_id)
    after = lifecycle_service.get(task.task_id)

    assert before == after


def test_check_is_deterministic_across_repeated_calls():
    lifecycle_service = LLMAgentTaskLifecycleService()
    task = _task_in_state(lifecycle_service, READY)
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)

    first = readiness_service.check(task.task_id)
    second = readiness_service.check(task.task_id)

    assert first == second
