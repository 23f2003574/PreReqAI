from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_effectiveness import LLMAgentStrategyOutcomeService
from backend.agent_strategy_library import LLMAgentStrategyService
from backend.agent_strategy_retrieval import LLMAgentStrategyRetriever
from backend.agent_strategy_scoring import LLMAgentStrategyScorer
from backend.agent_strategy_selection import LLMAgentStrategySelection, LLMAgentStrategySelector
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
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


class Harness:
    """One shared tool-calling pipeline wired to real Commit #1-#4 strategy
    services plus a Commit #5 LLMAgentStrategySelector -- the same minimal
    shape prior strategy test files already use."""

    def __init__(self):
        self.store = MultiPlanStore()

        registry = LLMToolRegistryService()
        registry.register("lookup", "Tool lookup", SCHEMA)
        registry.register("broken-lookup", "Tool broken-lookup", SCHEMA)

        invocation = LLMToolInvocationService(registry)
        permissions = LLMToolPermissionService(registry, invocation)
        permissions.register(
            LLMToolPermissionPolicy(policy_id="allow-lookup", tool_name="lookup", subject=ANY_SUBJECT, allowed=True)
        )
        permissions.register(
            LLMToolPermissionPolicy(
                policy_id="allow-broken-lookup", tool_name="broken-lookup", subject=ANY_SUBJECT, allowed=True
            )
        )

        execution = LLMToolExecutionService(registry, permissions)
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
            self.store, registry, permissions, invocation_service=invocation
        )
        step_execution = LLMAgentExecutionService(self.store, validation_service, orchestrator)
        self.plan_execution = LLMAgentPlanExecutionService(self.store, validation_service, step_execution)

        self.memory_service = LLMAgentMemoryService(self.plan_execution)
        self.strategy_service = LLMAgentStrategyService(self.memory_service)
        self.outcome_service = LLMAgentStrategyOutcomeService(self.strategy_service, self.plan_execution)
        self.scorer = LLMAgentStrategyScorer(self.strategy_service, self.outcome_service)
        self.retriever = LLMAgentStrategyRetriever(self.strategy_service)
        self.selector = LLMAgentStrategySelector(self.retriever, self.scorer)

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
        """Give strategy_id enough Commit #3 evidence to clear Commit #5's
        confidence gate."""
        for _ in range(successes):
            self.outcome(strategy_id, tool_name="lookup")
        for _ in range(failures):
            self.outcome(strategy_id, tool_name="broken-lookup")


def test_relevant_strategy_wins():
    harness = Harness()

    matching = harness.strategy(
        name="lookup-first", description="Always call the lookup tool before anything else"
    )
    harness.supported(matching.strategy_id, successes=1)

    unrelated = harness.strategy(
        name="cache-results", description="Cache repeated computations to avoid rework"
    )
    harness.supported(unrelated.strategy_id, successes=1)

    results = harness.selector.select("notebook-1", "lookup tool", now=NOW)

    assert [item.strategy.strategy_id for item in results][0] == matching.strategy_id
    assert results[0].relevance_score > results[-1].relevance_score


def test_effectiveness_affects_ranking():
    harness = Harness()

    proven = harness.strategy(name="proven", description="a reliable helper strategy")
    harness.supported(proven.strategy_id, successes=5)

    unreliable = harness.strategy(name="unreliable", description="a reliable helper strategy")
    harness.supported(unreliable.strategy_id, successes=0, failures=5)

    results = harness.selector.select("notebook-1", "reliable helper strategy", now=NOW)

    ids = [item.strategy.strategy_id for item in results]
    assert ids.index(proven.strategy_id) < ids.index(unreliable.strategy_id)


def test_archived_and_weak_strategies_excluded():
    harness = Harness()

    archived = harness.strategy(name="archived-strategy", description="lookup helper strategy")
    harness.supported(archived.strategy_id, successes=1)
    harness.strategy_service.archive(archived.strategy_id)

    weak = harness.strategy(name="weak-strategy", description="lookup helper strategy")
    # no outcomes recorded at all: zero evidence, zero confidence

    proven = harness.strategy(name="proven-strategy", description="lookup helper strategy")
    harness.supported(proven.strategy_id, successes=1)

    results = harness.selector.select("notebook-1", "lookup helper strategy", now=NOW)

    ids = {item.strategy.strategy_id for item in results}
    assert archived.strategy_id not in ids
    assert weak.strategy_id not in ids
    assert proven.strategy_id in ids


def test_scope_isolation():
    harness = Harness()

    strategy_1 = harness.strategy(scope_id="notebook-1", name="strategy-1", description="lookup helper")
    harness.supported(strategy_1.strategy_id, successes=1)

    strategy_2 = harness.strategy(scope_id="notebook-2", name="strategy-2", description="lookup helper")
    harness.supported(strategy_2.strategy_id, successes=1)

    results = harness.selector.select("notebook-1", "lookup helper", now=NOW)

    assert [item.strategy.strategy_id for item in results] == [strategy_1.strategy_id]


def test_limits():
    harness = Harness()

    created = []
    for index in range(4):
        strategy = harness.strategy(name=f"strategy-{index}", description="lookup helper strategy")
        harness.supported(strategy.strategy_id, successes=1)
        created.append(strategy)

    limited = harness.selector.select("notebook-1", "lookup helper strategy", limit=2, now=NOW)
    assert len(limited) == 2

    unlimited = harness.selector.select("notebook-1", "lookup helper strategy", now=NOW)
    assert len(unlimited) == 4

    with pytest.raises(ValueError):
        harness.selector.select("notebook-1", "lookup helper strategy", limit=0, now=NOW)


def test_deterministic_ties():
    harness = Harness()

    created = []
    for index in range(3):
        strategy = harness.strategy(name=f"strategy-{index}", description="identical relevance text")
        harness.supported(strategy.strategy_id, successes=1)
        created.append(strategy)

    first_call = harness.selector.select("notebook-1", "identical relevance", now=NOW)
    second_call = harness.selector.select("notebook-1", "identical relevance", now=NOW)

    first_ids = [item.strategy.strategy_id for item in first_call]
    assert first_ids == [item.strategy.strategy_id for item in second_call]

    expected = sorted(created, key=lambda item: (-item.created_at.timestamp(), item.strategy_id))
    assert first_ids == [item.strategy_id for item in expected]


def test_provenance():
    harness = Harness()

    memory = harness.memory(scope_id="notebook-1", content="proof content")
    strategy = harness.strategy_service.create(
        "notebook-1", "lookup-first", "Call lookup before anything else",
        {"steps": ["lookup"]}, [memory.memory_id],
    )
    harness.supported(strategy.strategy_id, successes=1)

    results = harness.selector.select("notebook-1", "lookup", now=NOW)

    assert len(results) == 1
    selection = results[0]
    assert isinstance(selection, LLMAgentStrategySelection)
    assert selection.strategy.strategy_id == strategy.strategy_id
    assert selection.strategy.source_memory_ids == [memory.memory_id]
    assert selection.effectiveness.strategy_id == strategy.strategy_id
    assert selection.effectiveness.evidence_count == 1
    assert selection.reason


def test_no_strategies_available():
    harness = Harness()

    assert harness.selector.select("empty-scope", "anything", now=NOW) == []

    strategy = harness.strategy(name="unsupported", description="lookup helper strategy")
    # zero outcomes -- excluded by the confidence gate
    assert harness.selector.select("notebook-1", "lookup helper strategy", now=NOW) == []
