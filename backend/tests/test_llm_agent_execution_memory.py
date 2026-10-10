from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import (
    IncompleteExecutionError,
    InvalidMemoryTypeError,
    LLMAgentMemory,
    LLMAgentMemoryService,
    NonMeaningfulOutcomeError,
    SecretContentError,
    UnknownAgentMemoryError,
)
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import FAILED, SUCCEEDED, LLMToolExecutionService
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


def always_fails(topic):
    raise RuntimeError("upstream lookup service is down")


class FixedPlanStore:
    def __init__(self, plan: LLMAgentPlan):
        self._plan = plan

    def get(self, plan_id: str) -> LLMAgentPlan:
        if plan_id != self._plan.plan_id:
            raise KeyError(plan_id)
        return self._plan


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


def _plan_execution_service(plan_id, tool_name, handler):
    """A real Commit #12 LLMAgentPlanExecutionService, wired with just enough
    of the existing tool-calling pipeline to run one bound step -- the same
    minimal `build()`/`wire()` shape backend/tests/test_llm_agent_execution_reporting.py
    already uses, trimmed to only what this commit's own tests need."""
    plan = _plan(plan_id, tool_name)
    store = FixedPlanStore(plan)

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


def test_record_and_get():
    plan_execution = _plan_execution_service("plan-1", "lookup", ok)
    execution = plan_execution.execute("plan-1", "user:ada")
    memory_service = LLMAgentMemoryService(plan_execution)

    recorded = memory_service.record(
        execution.execution_id,
        {"scope_id": "notebook-1", "memory_type": "strategy", "content": "call lookup with topic first"},
    )

    assert isinstance(recorded, LLMAgentMemory)
    assert recorded.memory_id is not None
    assert recorded.execution_id == execution.execution_id
    assert recorded.created_at is not None

    fetched = memory_service.get(recorded.memory_id)
    assert fetched.content == "call lookup with topic first"
    assert fetched.scope_id == "notebook-1"
    assert fetched.memory_type == "strategy"


def test_successful_outcome():
    plan_execution = _plan_execution_service("plan-1", "lookup", ok)
    execution = plan_execution.execute("plan-1", "user:ada")
    assert execution.status == SUCCEEDED
    memory_service = LLMAgentMemoryService(plan_execution)

    recorded = memory_service.record(
        execution.execution_id,
        {"scope_id": "notebook-1", "memory_type": "strategy", "content": "lookup succeeded first try"},
    )

    assert recorded.outcome == SUCCEEDED


def test_failed_outcome_handling():
    plan_execution = _plan_execution_service("plan-1", "lookup", always_fails)
    execution = plan_execution.execute("plan-1", "user:ada")
    assert execution.status == FAILED
    memory_service = LLMAgentMemoryService(plan_execution)

    recorded = memory_service.record(
        execution.execution_id,
        {"scope_id": "notebook-1", "memory_type": "failure_pattern", "content": "lookup fails when upstream is down"},
    )

    assert recorded.outcome == FAILED
    assert recorded.memory_type == "failure_pattern"


def test_incomplete_execution_is_not_recorded():
    plan_execution = _plan_execution_service("plan-1", "lookup", ok)
    memory_service = LLMAgentMemoryService(plan_execution)
    captured = {}

    def before_step(execution_id, step_id):
        captured["execution_id"] = execution_id
        with pytest.raises(IncompleteExecutionError):
            memory_service.record(
                execution_id, {"scope_id": "notebook-1", "memory_type": "strategy", "content": "too early"}
            )
        return True

    plan_execution.execute("plan-1", "user:ada", before_step=before_step)

    assert captured["execution_id"]
    # the guard never wrote anything, and never touched execution state
    assert memory_service.list("notebook-1") == []
    assert plan_execution.get(captured["execution_id"]).status == SUCCEEDED


def test_scope_isolation():
    plan_execution = _plan_execution_service("plan-1", "lookup", ok)
    execution = plan_execution.execute("plan-1", "user:ada")
    memory_service = LLMAgentMemoryService(plan_execution)

    memory_service.record(
        execution.execution_id,
        {"scope_id": "notebook-1", "memory_type": "strategy", "content": "belongs to notebook-1"},
    )
    memory_service.record(
        execution.execution_id,
        {"scope_id": "notebook-2", "memory_type": "strategy", "content": "belongs to notebook-2"},
    )

    notebook_1 = memory_service.list("notebook-1")
    notebook_2 = memory_service.list("notebook-2")

    assert [item.content for item in notebook_1] == ["belongs to notebook-1"]
    assert [item.content for item in notebook_2] == ["belongs to notebook-2"]


def test_type_filtering():
    plan_execution = _plan_execution_service("plan-1", "lookup", ok)
    execution = plan_execution.execute("plan-1", "user:ada")
    memory_service = LLMAgentMemoryService(plan_execution)

    memory_service.record(
        execution.execution_id,
        {"scope_id": "notebook-1", "memory_type": "strategy", "content": "a strategy"},
    )
    memory_service.record(
        execution.execution_id,
        {"scope_id": "notebook-1", "memory_type": "tool_usage", "content": "a tool usage note"},
    )

    strategies_only = memory_service.list("notebook-1", "strategy")
    assert [item.content for item in strategies_only] == ["a strategy"]

    with pytest.raises(InvalidMemoryTypeError):
        memory_service.list("notebook-1", "not-a-real-type")


def test_secret_exclusion():
    plan_execution = _plan_execution_service("plan-1", "lookup", ok)
    execution = plan_execution.execute("plan-1", "user:ada")
    memory_service = LLMAgentMemoryService(plan_execution)

    with pytest.raises(SecretContentError):
        memory_service.record(
            execution.execution_id,
            {"scope_id": "notebook-1", "memory_type": "strategy", "content": "here is my api_key: sk-abcdefghijklmnop"},
        )

    assert memory_service.list("notebook-1") == []


def test_missing_memory():
    plan_execution = _plan_execution_service("plan-1", "lookup", ok)
    memory_service = LLMAgentMemoryService(plan_execution)

    with pytest.raises(UnknownAgentMemoryError):
        memory_service.get("missing-id")

    assert memory_service.remove("missing-id") is False


def test_remove():
    plan_execution = _plan_execution_service("plan-1", "lookup", ok)
    execution = plan_execution.execute("plan-1", "user:ada")
    memory_service = LLMAgentMemoryService(plan_execution)

    recorded = memory_service.record(
        execution.execution_id,
        {"scope_id": "notebook-1", "memory_type": "strategy", "content": "to be removed"},
    )

    assert memory_service.remove(recorded.memory_id) is True
    with pytest.raises(UnknownAgentMemoryError):
        memory_service.get(recorded.memory_id)
    assert memory_service.remove(recorded.memory_id) is False
