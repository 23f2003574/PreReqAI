from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_library import ACTIVE, ARCHIVED, LLMAgentStrategyService
from backend.agent_strategy_retrieval import LLMAgentStrategyRetriever
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


def ok(topic):
    return {"topic": topic, "found": True}


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


def _plan_execution_service(store, tool_name, handler):
    registry = LLMToolRegistryService()
    registry.register(tool_name, f"Tool {tool_name}", SCHEMA)

    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    permissions.register(
        LLMToolPermissionPolicy(policy_id="allow-1", tool_name=tool_name, subject=ANY_SUBJECT, allowed=True)
    )

    execution = LLMToolExecutionService(registry, permissions)
    execution.bind(tool_name, handler)

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
        store, registry, permissions, invocation_service=invocation
    )
    step_execution = LLMAgentExecutionService(store, validation_service, orchestrator)
    return LLMAgentPlanExecutionService(store, validation_service, step_execution)


def _services():
    store = MultiPlanStore()
    plan_execution = _plan_execution_service(store, "lookup", ok)
    memory_service = LLMAgentMemoryService(plan_execution)
    strategy_service = LLMAgentStrategyService(memory_service)
    retriever = LLMAgentStrategyRetriever(strategy_service)
    return (plan_execution, store), memory_service, strategy_service, retriever


_plan_counter = [0]


def _memory(harness, memory_service, scope_id="notebook-1", content="call lookup with topic first"):
    plan_execution, store = harness
    _plan_counter[0] += 1
    plan_id = f"plan-{_plan_counter[0]}"
    store.add(_plan(plan_id, "lookup"))
    execution = plan_execution.execute(plan_id, "user:ada")
    return memory_service.record(
        execution.execution_id,
        {"scope_id": scope_id, "memory_type": "strategy", "content": content},
    )


def _strategy(harness, memory_service, strategy_service, scope_id, name, description, strategy_data):
    memory = _memory(harness, memory_service, scope_id=scope_id)
    return strategy_service.create(scope_id, name, description, strategy_data, [memory.memory_id])


def test_relevant_strategy_ranking():
    harness, memory_service, strategy_service, retriever = _services()

    matching = _strategy(
        harness, memory_service, strategy_service, "notebook-1",
        "lookup-first", "Always call the lookup tool before anything else", {"steps": ["lookup"]},
    )
    unrelated = _strategy(
        harness, memory_service, strategy_service, "notebook-1",
        "cache-results", "Cache repeated computations to avoid rework", {"steps": ["cache"]},
    )

    results = retriever.retrieve("notebook-1", "lookup tool")

    assert results[0].strategy_id == matching.strategy_id
    assert results[-1].strategy_id == unrelated.strategy_id


def test_scope_isolation():
    harness, memory_service, strategy_service, retriever = _services()

    _strategy(
        harness, memory_service, strategy_service, "notebook-1",
        "strategy-1", "belongs to notebook-1", {"steps": ["a"]},
    )
    _strategy(
        harness, memory_service, strategy_service, "notebook-2",
        "strategy-2", "belongs to notebook-2", {"steps": ["b"]},
    )

    results = retriever.retrieve("notebook-1", "belongs")

    assert [item.name for item in results] == ["strategy-1"]


def test_archived_excluded_by_default():
    harness, memory_service, strategy_service, retriever = _services()

    active = _strategy(
        harness, memory_service, strategy_service, "notebook-1",
        "active-strategy", "an active strategy", {"steps": ["a"]},
    )
    archived = _strategy(
        harness, memory_service, strategy_service, "notebook-1",
        "archived-strategy", "an archived strategy", {"steps": ["b"]},
    )
    strategy_service.archive(archived.strategy_id)

    default_results = retriever.retrieve("notebook-1", "strategy")
    assert [item.strategy_id for item in default_results] == [active.strategy_id]

    archived_only = retriever.retrieve("notebook-1", "strategy", status=ARCHIVED)
    assert [item.strategy_id for item in archived_only] == [archived.strategy_id]

    explicit_active = retriever.retrieve("notebook-1", "strategy", status=ACTIVE)
    assert [item.strategy_id for item in explicit_active] == [active.strategy_id]


def test_limit_handling():
    harness, memory_service, strategy_service, retriever = _services()

    for index in range(5):
        _strategy(
            harness, memory_service, strategy_service, "notebook-1",
            f"strategy-{index}", "a matching strategy", {"steps": [str(index)]},
        )

    limited = retriever.retrieve("notebook-1", "matching", limit=2)
    assert len(limited) == 2

    unlimited = retriever.retrieve("notebook-1", "matching")
    assert len(unlimited) == 5

    with pytest.raises(ValueError):
        retriever.retrieve("notebook-1", "matching", limit=0)

    with pytest.raises(ValueError):
        retriever.retrieve("notebook-1", "matching", limit=-1)


def test_empty_results():
    harness, memory_service, strategy_service, retriever = _services()

    assert retriever.retrieve("empty-scope", "anything") == []

    _strategy(
        harness, memory_service, strategy_service, "notebook-1",
        "strategy-1", "totally unrelated topic", {"steps": ["a"]},
    )

    # a query with no overlapping terms still returns every scope match,
    # just all scored 0.0 and ordered by recency then strategy_id
    results = retriever.retrieve("notebook-1", "quantum entanglement")
    assert len(results) == 1


def test_deterministic_ordering():
    harness, memory_service, strategy_service, retriever = _services()

    created = [
        _strategy(
            harness, memory_service, strategy_service, "notebook-1",
            f"strategy-{index}", "identical relevance text", {"steps": [str(index)]},
        )
        for index in range(3)
    ]

    first_call = retriever.retrieve("notebook-1", "identical relevance")
    second_call = retriever.retrieve("notebook-1", "identical relevance")

    assert [item.strategy_id for item in first_call] == [item.strategy_id for item in second_call]

    # every candidate scores identically on relevance, so the tie is
    # broken by most-recently-created first, then strategy_id
    expected = sorted(created, key=lambda item: (-item.created_at.timestamp(), item.strategy_id))
    assert [item.strategy_id for item in first_call] == [item.strategy_id for item in expected]


def test_provenance():
    harness, memory_service, strategy_service, retriever = _services()

    memory = _memory(harness, memory_service, scope_id="notebook-1", content="proof content")
    created = strategy_service.create(
        "notebook-1", "lookup-first", "Call lookup before anything else",
        {"steps": ["lookup"]}, [memory.memory_id],
    )

    results = retriever.retrieve("notebook-1", "lookup")
    assert results[0].source_memory_ids == [memory.memory_id]

    provenance = strategy_service.provenance(results[0].strategy_id)
    assert [item.memory_id for item in provenance] == [memory.memory_id]
