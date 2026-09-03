import dataclasses
import json
from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_application import (
    CONTEXT_KEY,
    CrossScopeApplicationError,
    LLMAgentStrategyApplicator,
)
from backend.agent_strategy_effectiveness import LLMAgentStrategyOutcomeService
from backend.agent_strategy_library import ARCHIVED, LLMAgentStrategyService
from backend.agent_strategy_retrieval import LLMAgentStrategyRetriever
from backend.agent_strategy_scoring import LLMAgentStrategyScorer
from backend.agent_strategy_selection import LLMAgentStrategySelector
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanningService, LLMAgentPlanStep
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import LLMToolExecutionService
from backend.llm.tool_idempotency import LLMToolIdempotencyService
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_orchestration import LLMToolCallingOrchestrationService
from backend.llm.tool_permissions import ANY_SUBJECT, LLMToolPermissionPolicy, LLMToolPermissionService
from backend.llm.tool_results import LLMToolResultService
from backend.llm.tool_retry import LLMToolRetryPolicy, LLMToolRetryService
from backend.llm.tools import LLMToolRegistryService

SCHEMA = {
    "type": "object",
    "properties": {"topic": {"type": "string"}},
    "required": ["topic"],
}

NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


def ok(topic):
    return {"topic": topic, "found": True}


def always_fails(topic):
    raise RuntimeError("upstream lookup service is down")


class MultiPlanStore:
    def __init__(self):
        self._plans = {}

    def add(self, plan: LLMAgentPlan):
        self._plans[plan.plan_id] = plan

    def get(self, plan_id: str) -> LLMAgentPlan:
        return self._plans[plan_id]


def _step(step_id, tool_name):
    return LLMAgentPlanStep(
        step_id=step_id, action=f"call {tool_name}", tool_name=tool_name,
        arguments={"topic": "linear algebra"}, depends_on=[], status=READY, errors=[],
    )


def _plan(plan_id, tool_name):
    return LLMAgentPlan(
        plan_id=plan_id, task="a test task", steps=[_step("step-1", tool_name)],
        status=READY, created_at=datetime.now(timezone.utc),
    )


class ScriptedProvider(LLMProvider):
    def __init__(self, script):
        self._script = list(script)
        self.calls = 0
        self.last_request = None

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        self.calls += 1
        self.last_request = request
        return self._script[min(self.calls - 1, len(self._script) - 1)]

    def stream(self, request):
        raise NotImplementedError


def _make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


PLAN_SCRIPT = [
    _make_response(json.dumps({"steps": [{"action": "look it up", "tool": "lookup", "arguments": {}}]}))
]


class Harness:
    """One shared tool-calling pipeline wired to real Commit #1-#5 strategy
    services plus a Commit #6 LLMAgentStrategyApplicator, and a real
    LLMAgentPlanningService driven by a ScriptedProvider -- the same
    minimal shape backend/tests/test_llm_agent_memory_aware_planning.py
    already uses for memory."""

    def __init__(self):
        self.store = MultiPlanStore()

        self.registry = LLMToolRegistryService()
        self.registry.register("lookup", "Tool lookup", SCHEMA)
        self.registry.register("broken-lookup", "Tool broken-lookup", SCHEMA)

        invocation = LLMToolInvocationService(self.registry)
        permissions = LLMToolPermissionService(self.registry, invocation)
        permissions.register(
            LLMToolPermissionPolicy(policy_id="allow-lookup", tool_name="lookup", subject=ANY_SUBJECT, allowed=True)
        )
        permissions.register(
            LLMToolPermissionPolicy(
                policy_id="allow-broken-lookup", tool_name="broken-lookup", subject=ANY_SUBJECT, allowed=True
            )
        )

        execution = LLMToolExecutionService(self.registry, permissions)
        execution.bind("lookup", ok)
        execution.bind("broken-lookup", always_fails)

        idempotency = LLMToolIdempotencyService(execution, permissions)
        control = LLMToolExecutionControlService(execution, idempotency)
        retry = LLMToolRetryService(
            control, execution, LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
            sleeper=lambda seconds: None, idempotency_service=idempotency,
        )
        results = LLMToolResultService()
        orchestrator = LLMToolCallingOrchestrationService(
            invocation_service=invocation, permission_service=permissions, execution_service=execution,
            result_service=results, idempotency_service=idempotency, control_service=control,
            retry_service=retry,
        )

        validation_service = LLMAgentPlanValidationService(
            self.store, self.registry, permissions, invocation_service=invocation
        )
        step_execution = LLMAgentExecutionService(self.store, validation_service, orchestrator)
        self.plan_execution = LLMAgentPlanExecutionService(self.store, validation_service, step_execution)

        self.memory_service = LLMAgentMemoryService(self.plan_execution)
        self.strategy_service = LLMAgentStrategyService(self.memory_service)
        self.outcome_service = LLMAgentStrategyOutcomeService(self.strategy_service, self.plan_execution)
        self.scorer = LLMAgentStrategyScorer(self.strategy_service, self.outcome_service)
        self.retriever = LLMAgentStrategyRetriever(self.strategy_service)
        self.selector = LLMAgentStrategySelector(self.retriever, self.scorer)
        self.applicator = LLMAgentStrategyApplicator()

        self._plan_counter = 0

    def run(self, tool_name="lookup", plan_id=None):
        if plan_id is None:
            self._plan_counter += 1
            plan_id = f"plan-{self._plan_counter}"
        self.store.add(_plan(plan_id, tool_name))
        return self.plan_execution.execute(plan_id, "user:ada")

    def memory(self, scope_id="notebook-1", tool_name="lookup", content="call lookup with topic first"):
        execution = self.run(tool_name=tool_name)
        return self.memory_service.record(
            execution.execution_id,
            {"scope_id": scope_id, "memory_type": "strategy", "content": content},
        )

    def strategy(self, scope_id="notebook-1", name="lookup-first", description="Call lookup first"):
        memory = self.memory(scope_id=scope_id)
        return self.strategy_service.create(
            scope_id, name, description, {"steps": ["lookup"]}, [memory.memory_id]
        )

    def outcome(self, strategy_id, tool_name="lookup"):
        execution = self.run(tool_name=tool_name)
        return self.outcome_service.record(strategy_id, execution.execution_id)

    def supported(self, strategy_id, successes=1, failures=0):
        for _ in range(successes):
            self.outcome(strategy_id, tool_name="lookup")
        for _ in range(failures):
            self.outcome(strategy_id, tool_name="broken-lookup")

    def select(self, scope_id, task_context, **kwargs):
        return self.selector.select(scope_id, task_context, now=NOW, **kwargs)

    def planning_service(self, script):
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
            context_service=context_service, routing_service=routing_service, providers={"openai": provider},
        )
        return LLMAgentPlanningService(self.registry, orchestration_service, context_service), provider


def test_selected_strategies_reach_planner():
    harness = Harness()
    strategy = harness.strategy(description="Always call the lookup tool before anything else")
    harness.supported(strategy.strategy_id, successes=1)

    selected = harness.select("notebook-1", "lookup tool")
    enriched_context = harness.applicator.apply(None, selected)

    planning_service, provider = harness.planning_service(PLAN_SCRIPT)
    plan = planning_service.create("lookup tool", enriched_context)

    assert plan.status == READY
    sent_context = json.loads(provider.last_request.messages[-1]["content"])["context"]
    assert sent_context[CONTEXT_KEY][0]["strategy_id"] == strategy.strategy_id


def test_scores_and_provenance_preserved():
    harness = Harness()
    memory = harness.memory(scope_id="notebook-1", content="proof content")
    strategy = harness.strategy_service.create(
        "notebook-1", "lookup-first", "Call lookup before anything else",
        {"steps": ["lookup"]}, [memory.memory_id],
    )
    harness.supported(strategy.strategy_id, successes=1)

    selected = harness.select("notebook-1", "lookup")
    enriched_context = harness.applicator.apply({}, selected)

    entry = enriched_context[CONTEXT_KEY][0]
    selection = selected[0]

    assert entry["strategy_id"] == strategy.strategy_id
    assert entry["relevance_score"] == selection.relevance_score
    assert entry["combined_score"] == selection.combined_score
    assert entry["effectiveness"]["score"] == selection.effectiveness.score
    assert entry["effectiveness"]["confidence"] == selection.effectiveness.confidence
    assert entry["effectiveness"]["evidence_count"] == 1
    assert entry["provenance"]["source_memory_ids"] == [memory.memory_id]
    assert entry["advisory"] is True


def test_scope_isolation():
    harness = Harness()
    strategy_1 = harness.strategy(scope_id="notebook-1", name="strategy-1", description="lookup helper")
    harness.supported(strategy_1.strategy_id, successes=1)
    strategy_2 = harness.strategy(scope_id="notebook-2", name="strategy-2", description="lookup helper")
    harness.supported(strategy_2.strategy_id, successes=1)

    selected = harness.select("notebook-1", "lookup helper")
    enriched_context = harness.applicator.apply(None, selected)

    ids = [entry["strategy_id"] for entry in enriched_context[CONTEXT_KEY]]
    assert ids == [strategy_1.strategy_id]

    # a caller who (incorrectly) mixes selections from two different
    # scopes is refused outright, never silently merged
    with pytest.raises(CrossScopeApplicationError):
        harness.applicator.apply(None, list(selected) + list(harness.select("notebook-2", "lookup helper")))


def test_archived_exclusion():
    harness = Harness()
    strategy = harness.strategy(description="lookup helper")
    harness.supported(strategy.strategy_id, successes=1)

    selected = harness.select("notebook-1", "lookup helper")
    assert len(selected) == 1

    # a selection is a point-in-time snapshot: archiving the strategy
    # afterwards never mutates it, so simulate a stale selection still
    # carrying the now-archived strategy directly
    stale_selection = selected[0]
    archived_strategy = dataclasses.replace(stale_selection.strategy, status=ARCHIVED)
    stale_selection = dataclasses.replace(stale_selection, strategy=archived_strategy)

    enriched_context = harness.applicator.apply(None, [stale_selection])

    assert enriched_context[CONTEXT_KEY] == []


def test_conflicting_strategies():
    harness = Harness()
    succeeded = harness.strategy(name="succeeded-strategy", description="lookup helper strategy")
    harness.supported(succeeded.strategy_id, successes=5)

    failed = harness.strategy(name="failed-strategy", description="lookup helper strategy")
    harness.supported(failed.strategy_id, successes=0, failures=5)

    selected = harness.select("notebook-1", "lookup helper strategy")
    enriched_context = harness.applicator.apply(None, selected)

    ids = {entry["strategy_id"] for entry in enriched_context[CONTEXT_KEY]}
    # both sides of the disagreement remain visible, neither suppressed --
    # the applicator never resolves the conflict itself
    assert succeeded.strategy_id in ids
    assert failed.strategy_id in ids


def test_empty_selection():
    harness = Harness()

    enriched_context = harness.applicator.apply({"existing": "value"}, [])

    assert enriched_context == {"existing": "value", CONTEXT_KEY: []}


def test_existing_planning_behavior_unchanged():
    harness = Harness()
    # no strategy recorded at all -- strategy-applied planning should
    # behave exactly like calling the real planner directly with the same
    # script

    direct_service, direct_provider = harness.planning_service(PLAN_SCRIPT)
    direct_plan = direct_service.create("explain lookup")

    aware_service, aware_provider = harness.planning_service(PLAN_SCRIPT)
    enriched_context = harness.applicator.apply(None, [])
    aware_plan = aware_service.create("explain lookup", enriched_context)

    assert aware_plan.status == direct_plan.status
    assert [s.tool_name for s in aware_plan.steps] == [s.tool_name for s in direct_plan.steps]
    assert [s.action for s in aware_plan.steps] == [s.action for s in direct_plan.steps]
