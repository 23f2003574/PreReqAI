from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService, UnknownAgentPlanExecutionError
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_library import LLMAgentStrategyService, UnknownAgentStrategyError
from backend.agent_strategy_usage import (
    InvalidAppliedFlagError,
    InvalidSelectionScoreError,
    LLMAgentStrategyUsage,
    LLMAgentStrategyUsageService,
    UnknownAgentStrategyUsageError,
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


class Harness:
    def __init__(self):
        self.store = MultiPlanStore()

        registry = LLMToolRegistryService()
        registry.register("lookup", "Tool lookup", SCHEMA)

        invocation = LLMToolInvocationService(registry)
        permissions = LLMToolPermissionService(registry, invocation)
        permissions.register(
            LLMToolPermissionPolicy(policy_id="allow-1", tool_name="lookup", subject=ANY_SUBJECT, allowed=True)
        )

        execution = LLMToolExecutionService(registry, permissions)
        execution.bind("lookup", ok)

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
        self.usage_service = LLMAgentStrategyUsageService(self.strategy_service, self.plan_execution)

        self._plan_counter = 0

    def run(self, plan_id=None):
        if plan_id is None:
            self._plan_counter += 1
            plan_id = f"plan-{self._plan_counter}"
        self.store.add(_plan(plan_id, "lookup"))
        return self.plan_execution.execute(plan_id, "user:ada")

    def memory(self, scope_id="notebook-1", content="call lookup with topic first"):
        execution = self.run()
        return self.memory_service.record(
            execution.execution_id,
            {"scope_id": scope_id, "memory_type": "strategy", "content": content},
        )

    def strategy(self, scope_id="notebook-1", name="lookup-first", description="Call lookup first"):
        memory = self.memory(scope_id=scope_id)
        return self.strategy_service.create(
            scope_id, name, description, {"steps": ["lookup"]}, [memory.memory_id]
        )


def test_usage_recording():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run()

    usage = harness.usage_service.record(
        strategy.strategy_id, execution.execution_id, selection_score=0.85, applied=True
    )

    assert isinstance(usage, LLMAgentStrategyUsage)
    assert usage.usage_id is not None
    assert usage.strategy_id == strategy.strategy_id
    assert usage.execution_id == execution.execution_id
    assert usage.selection_score == 0.85
    assert usage.applied is True
    assert usage.created_at is not None

    fetched = harness.usage_service.get(usage.usage_id)
    assert fetched.usage_id == usage.usage_id


def test_selected_vs_applied():
    harness = Harness()
    strategy = harness.strategy()

    selected_only_execution = harness.run()
    applied_execution = harness.run()

    selected_only = harness.usage_service.record(
        strategy.strategy_id, selected_only_execution.execution_id, selection_score=0.4, applied=False
    )
    applied = harness.usage_service.record(
        strategy.strategy_id, applied_execution.execution_id, selection_score=0.9, applied=True
    )

    usages = harness.usage_service.list_for_strategy(strategy.strategy_id)
    by_execution = {usage.execution_id: usage for usage in usages}

    assert by_execution[selected_only.execution_id].applied is False
    assert by_execution[applied.execution_id].applied is True


def test_duplicate_usage_is_idempotent():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run()

    first = harness.usage_service.record(
        strategy.strategy_id, execution.execution_id, selection_score=0.5, applied=False
    )
    second = harness.usage_service.record(
        strategy.strategy_id, execution.execution_id, selection_score=0.99, applied=True
    )

    assert first.usage_id == second.usage_id
    # the original selection metadata is preserved -- the second call is
    # a no-op, never an overwrite
    assert second.selection_score == 0.5
    assert second.applied is False

    usages = harness.usage_service.list_for_strategy(strategy.strategy_id)
    assert len(usages) == 1


def test_scope_isolation():
    harness = Harness()
    strategy_a = harness.strategy(scope_id="notebook-1", name="strategy-a")
    strategy_b = harness.strategy(scope_id="notebook-2", name="strategy-b")

    execution_a = harness.run()
    execution_b = harness.run()

    harness.usage_service.record(strategy_a.strategy_id, execution_a.execution_id, selection_score=0.7, applied=True)
    harness.usage_service.record(strategy_b.strategy_id, execution_b.execution_id, selection_score=0.7, applied=True)

    usages_a = harness.usage_service.list_for_strategy(strategy_a.strategy_id)
    usages_b = harness.usage_service.list_for_strategy(strategy_b.strategy_id)

    assert [item.execution_id for item in usages_a] == [execution_a.execution_id]
    assert [item.execution_id for item in usages_b] == [execution_b.execution_id]


def test_missing_references():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run()

    with pytest.raises(UnknownAgentStrategyError):
        harness.usage_service.record("missing-strategy", execution.execution_id, selection_score=0.5, applied=True)

    with pytest.raises(UnknownAgentPlanExecutionError):
        harness.usage_service.record(strategy.strategy_id, "missing-execution", selection_score=0.5, applied=True)

    with pytest.raises(UnknownAgentStrategyError):
        harness.usage_service.list_for_strategy("missing-strategy")

    with pytest.raises(UnknownAgentPlanExecutionError):
        harness.usage_service.list_for_execution("missing-execution")

    with pytest.raises(UnknownAgentStrategyUsageError):
        harness.usage_service.get("missing-usage")


def test_execution_and_strategy_history():
    harness = Harness()
    strategy_1 = harness.strategy(name="strategy-1")
    strategy_2 = harness.strategy(name="strategy-2")

    shared_execution = harness.run()
    harness.usage_service.record(strategy_1.strategy_id, shared_execution.execution_id, selection_score=0.6, applied=True)
    harness.usage_service.record(strategy_2.strategy_id, shared_execution.execution_id, selection_score=0.3, applied=False)

    other_execution = harness.run()
    harness.usage_service.record(strategy_1.strategy_id, other_execution.execution_id, selection_score=0.8, applied=True)

    for_execution = harness.usage_service.list_for_execution(shared_execution.execution_id)
    assert {item.strategy_id for item in for_execution} == {strategy_1.strategy_id, strategy_2.strategy_id}

    for_strategy_1 = harness.usage_service.list_for_strategy(strategy_1.strategy_id)
    assert [item.execution_id for item in for_strategy_1] == [
        shared_execution.execution_id, other_execution.execution_id
    ]

    for_strategy_2 = harness.usage_service.list_for_strategy(strategy_2.strategy_id)
    assert [item.execution_id for item in for_strategy_2] == [shared_execution.execution_id]


def test_validation():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run()

    with pytest.raises(InvalidSelectionScoreError):
        harness.usage_service.record(strategy.strategy_id, execution.execution_id, selection_score=1.5, applied=True)

    with pytest.raises(InvalidSelectionScoreError):
        harness.usage_service.record(strategy.strategy_id, execution.execution_id, selection_score="high", applied=True)

    with pytest.raises(InvalidAppliedFlagError):
        harness.usage_service.record(strategy.strategy_id, execution.execution_id, selection_score=0.5, applied="yes")
