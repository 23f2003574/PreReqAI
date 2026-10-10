from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_library import (
    ACTIVE,
    ARCHIVED,
    ArchivedStrategyError,
    CrossScopeProvenanceError,
    EmptyProvenanceError,
    InvalidStrategyDataError,
    LLMAgentStrategy,
    LLMAgentStrategyService,
    SecretStrategyDataError,
    UnknownAgentStrategyError,
)
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
    """A real Commit #12 LLMAgentPlanExecutionService, wired with just enough
    of the existing tool-calling pipeline to run bound steps -- the same
    minimal shape backend/tests/test_llm_agent_memory_promotion.py already
    uses, so multiple plans can be executed against one shared service."""
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


def _memory(harness, memory_service, scope_id="notebook-1", plan_id="plan-1", content="call lookup with topic first"):
    plan_execution, store = harness
    store.add(_plan(plan_id, "lookup"))
    execution = plan_execution.execute(plan_id, "user:ada")
    return memory_service.record(
        execution.execution_id,
        {"scope_id": scope_id, "memory_type": "strategy", "content": content},
    )


def _services():
    store = MultiPlanStore()
    plan_execution = _plan_execution_service(store, "lookup", ok)
    memory_service = LLMAgentMemoryService(plan_execution)
    strategy_service = LLMAgentStrategyService(memory_service)
    return (plan_execution, store), memory_service, strategy_service


def test_create_and_get():
    harness, memory_service, strategy_service = _services()
    memory = _memory(harness, memory_service)

    created = strategy_service.create(
        "notebook-1", "lookup-first", "Call lookup before anything else",
        {"steps": ["lookup"]}, [memory.memory_id],
    )

    assert isinstance(created, LLMAgentStrategy)
    assert created.strategy_id is not None
    assert created.status == ACTIVE
    assert created.source_memory_ids == [memory.memory_id]
    assert created.created_at is not None
    assert created.updated_at is not None

    fetched = strategy_service.get(created.strategy_id)
    assert fetched.name == "lookup-first"
    assert fetched.strategy_data == {"steps": ["lookup"]}


def test_missing_strategy():
    _, _, strategy_service = _services()

    with pytest.raises(UnknownAgentStrategyError):
        strategy_service.get("missing-id")

    with pytest.raises(UnknownAgentStrategyError):
        strategy_service.update("missing-id", name="new name")

    with pytest.raises(UnknownAgentStrategyError):
        strategy_service.archive("missing-id")


def test_crud_lifecycle():
    harness, memory_service, strategy_service = _services()
    memory = _memory(harness, memory_service)

    created = strategy_service.create(
        "notebook-1", "lookup-first", "Call lookup before anything else",
        {"steps": ["lookup"]}, [memory.memory_id],
    )

    updated = strategy_service.update(
        created.strategy_id, description="Always call lookup first", strategy_data={"steps": ["lookup", "verify"]}
    )
    assert updated.description == "Always call lookup first"
    assert updated.strategy_data == {"steps": ["lookup", "verify"]}
    assert updated.name == "lookup-first"
    assert updated.status == ACTIVE

    archived = strategy_service.archive(created.strategy_id)
    assert archived.status == ARCHIVED

    still_there = strategy_service.get(created.strategy_id)
    assert still_there.status == ARCHIVED


def test_scope_isolation():
    harness, memory_service, strategy_service = _services()
    memory_1 = _memory(harness, memory_service, scope_id="notebook-1", plan_id="plan-1")
    memory_2 = _memory(harness, memory_service, scope_id="notebook-2", plan_id="plan-2")

    strategy_service.create(
        "notebook-1", "strategy-1", "belongs to notebook-1", {"steps": ["a"]}, [memory_1.memory_id]
    )
    strategy_service.create(
        "notebook-2", "strategy-2", "belongs to notebook-2", {"steps": ["b"]}, [memory_2.memory_id]
    )

    notebook_1 = strategy_service.list("notebook-1")
    notebook_2 = strategy_service.list("notebook-2")

    assert [item.name for item in notebook_1] == ["strategy-1"]
    assert [item.name for item in notebook_2] == ["strategy-2"]


def test_cross_scope_provenance_rejected():
    harness, memory_service, strategy_service = _services()
    other_scope_memory = _memory(harness, memory_service, scope_id="notebook-2", plan_id="plan-2")

    with pytest.raises(CrossScopeProvenanceError):
        strategy_service.create(
            "notebook-1", "bad-strategy", "cites a memory from another scope",
            {"steps": ["a"]}, [other_scope_memory.memory_id],
        )


def test_validation():
    harness, memory_service, strategy_service = _services()
    memory = _memory(harness, memory_service)

    with pytest.raises(ValueError):
        strategy_service.create("", "name", "description", {"steps": ["a"]}, [memory.memory_id])

    with pytest.raises(ValueError):
        strategy_service.create("notebook-1", "", "description", {"steps": ["a"]}, [memory.memory_id])

    with pytest.raises(InvalidStrategyDataError):
        strategy_service.create("notebook-1", "name", "description", {}, [memory.memory_id])

    with pytest.raises(EmptyProvenanceError):
        strategy_service.create("notebook-1", "name", "description", {"steps": ["a"]}, [])

    with pytest.raises(SecretStrategyDataError):
        strategy_service.create(
            "notebook-1", "name", "description",
            {"note": "api_key: sk-abcdefghijklmnop"}, [memory.memory_id],
        )

    with pytest.raises(KeyError):
        strategy_service.create("notebook-1", "name", "description", {"steps": ["a"]}, ["missing-memory-id"])


def test_archive_behavior():
    harness, memory_service, strategy_service = _services()
    memory = _memory(harness, memory_service)

    created = strategy_service.create(
        "notebook-1", "lookup-first", "Call lookup before anything else",
        {"steps": ["lookup"]}, [memory.memory_id],
    )

    archived_once = strategy_service.archive(created.strategy_id)
    assert archived_once.status == ARCHIVED

    # archiving an already-archived strategy is a no-op, not an error
    archived_twice = strategy_service.archive(created.strategy_id)
    assert archived_twice.status == ARCHIVED

    with pytest.raises(ArchivedStrategyError):
        strategy_service.update(created.strategy_id, name="renamed")

    # archived strategies remain listable, never deleted
    still_listed = strategy_service.list("notebook-1", status=ARCHIVED)
    assert [item.strategy_id for item in still_listed] == [created.strategy_id]


def test_provenance():
    harness, memory_service, strategy_service = _services()
    memory_1 = _memory(harness, memory_service, plan_id="plan-1", content="first proof")
    memory_2 = _memory(harness, memory_service, plan_id="plan-2", content="second proof")

    created = strategy_service.create(
        "notebook-1", "two-step", "Justified by two memories",
        {"steps": ["lookup", "verify"]}, [memory_1.memory_id, memory_2.memory_id],
    )

    provenance = strategy_service.provenance(created.strategy_id)
    assert [item.memory_id for item in provenance] == [memory_1.memory_id, memory_2.memory_id]
    assert [item.content for item in provenance] == ["first proof", "second proof"]
