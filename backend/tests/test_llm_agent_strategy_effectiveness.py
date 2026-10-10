from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService, UnknownAgentPlanExecutionError
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_effectiveness import (
    IncompleteExecutionError,
    InvalidEvidenceError,
    LLMAgentStrategyOutcome,
    LLMAgentStrategyOutcomeService,
    NonMeaningfulOutcomeError,
    SecretEvidenceError,
    UnknownAgentStrategyOutcomeError,
)
from backend.agent_strategy_library import LLMAgentStrategyService, UnknownAgentStrategyError
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


class Harness:
    """One shared tool-calling pipeline that can run both successful and
    failing plans, wired to real Commit #1/memory/strategy/plan-execution
    services -- the same minimal shape prior strategy-library/-retrieval
    test files already use, extended with a second (always-failing) tool
    so effectiveness tests can produce both SUCCEEDED and FAILED
    executions against the same strategy."""

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


def test_outcome_recording():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run()

    outcome = harness.outcome_service.record(strategy.strategy_id, execution.execution_id, evidence={"note": "ran cleanly"})

    assert isinstance(outcome, LLMAgentStrategyOutcome)
    assert outcome.outcome_id is not None
    assert outcome.strategy_id == strategy.strategy_id
    assert outcome.execution_id == execution.execution_id
    assert outcome.result == SUCCEEDED
    assert outcome.evidence == {"note": "ran cleanly"}
    assert outcome.created_at is not None

    fetched = harness.outcome_service.get(outcome.outcome_id)
    assert fetched.outcome_id == outcome.outcome_id


def test_success_failure_aggregation():
    harness = Harness()
    strategy = harness.strategy()

    success_execution = harness.run(tool_name="lookup")
    failure_execution = harness.run(tool_name="broken-lookup")
    assert success_execution.status == SUCCEEDED
    assert failure_execution.status == FAILED

    harness.outcome_service.record(strategy.strategy_id, success_execution.execution_id)
    harness.outcome_service.record(strategy.strategy_id, failure_execution.execution_id)

    summary = harness.outcome_service.summarize(strategy.strategy_id)

    assert summary.strategy_id == strategy.strategy_id
    assert summary.total_outcomes == 2
    assert summary.succeeded_count == 1
    assert summary.failed_count == 1
    assert summary.success_rate == 0.5
    assert summary.last_outcome_at is not None


def test_duplicate_prevention():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run()

    first = harness.outcome_service.record(strategy.strategy_id, execution.execution_id, evidence={"note": "first"})
    second = harness.outcome_service.record(strategy.strategy_id, execution.execution_id, evidence={"note": "second"})

    assert first.outcome_id == second.outcome_id
    # the original evidence is preserved -- the second call is a no-op,
    # never an overwrite
    assert second.evidence == {"note": "first"}

    outcomes = harness.outcome_service.list_for_strategy(strategy.strategy_id)
    assert len(outcomes) == 1

    summary = harness.outcome_service.summarize(strategy.strategy_id)
    assert summary.total_outcomes == 1


def test_scope_isolation():
    harness = Harness()
    strategy_a = harness.strategy(scope_id="notebook-1", name="strategy-a")
    strategy_b = harness.strategy(scope_id="notebook-2", name="strategy-b")

    execution_a = harness.run()
    execution_b = harness.run()

    harness.outcome_service.record(strategy_a.strategy_id, execution_a.execution_id)
    harness.outcome_service.record(strategy_b.strategy_id, execution_b.execution_id)

    outcomes_a = harness.outcome_service.list_for_strategy(strategy_a.strategy_id)
    outcomes_b = harness.outcome_service.list_for_strategy(strategy_b.strategy_id)

    assert [item.execution_id for item in outcomes_a] == [execution_a.execution_id]
    assert [item.execution_id for item in outcomes_b] == [execution_b.execution_id]

    summary_a = harness.outcome_service.summarize(strategy_a.strategy_id)
    summary_b = harness.outcome_service.summarize(strategy_b.strategy_id)
    assert summary_a.total_outcomes == 1
    assert summary_b.total_outcomes == 1


def test_missing_references():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run()

    with pytest.raises(UnknownAgentStrategyError):
        harness.outcome_service.record("missing-strategy", execution.execution_id)

    with pytest.raises(UnknownAgentPlanExecutionError):
        harness.outcome_service.record(strategy.strategy_id, "missing-execution")

    with pytest.raises(UnknownAgentStrategyError):
        harness.outcome_service.list_for_strategy("missing-strategy")

    with pytest.raises(UnknownAgentStrategyError):
        harness.outcome_service.summarize("missing-strategy")

    with pytest.raises(UnknownAgentStrategyOutcomeError):
        harness.outcome_service.get("missing-outcome")


def test_incomplete_execution_is_not_recorded():
    harness = Harness()
    strategy = harness.strategy()
    captured = {}

    def before_step(execution_id, step_id):
        captured["execution_id"] = execution_id
        with pytest.raises(IncompleteExecutionError):
            harness.outcome_service.record(strategy.strategy_id, execution_id)
        return True

    harness.store.add(_plan("plan-incomplete", "lookup"))
    harness.plan_execution.execute("plan-incomplete", "user:ada", before_step=before_step)

    assert captured["execution_id"]
    assert harness.outcome_service.list_for_strategy(strategy.strategy_id) == []
    assert harness.plan_execution.get(captured["execution_id"]).status == SUCCEEDED


def test_historical_preservation():
    harness = Harness()
    strategy = harness.strategy()

    first_execution = harness.run()
    second_execution = harness.run(tool_name="broken-lookup")

    first_outcome = harness.outcome_service.record(strategy.strategy_id, first_execution.execution_id, evidence={"attempt": 1})
    second_outcome = harness.outcome_service.record(strategy.strategy_id, second_execution.execution_id, evidence={"attempt": 2})

    outcomes = harness.outcome_service.list_for_strategy(strategy.strategy_id)
    assert [item.outcome_id for item in outcomes] == [first_outcome.outcome_id, second_outcome.outcome_id]
    assert [item.result for item in outcomes] == [SUCCEEDED, FAILED]
    assert [item.evidence for item in outcomes] == [{"attempt": 1}, {"attempt": 2}]


def test_evidence_validation():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run()

    with pytest.raises(InvalidEvidenceError):
        harness.outcome_service.record(strategy.strategy_id, execution.execution_id, evidence={"bad": object()})

    with pytest.raises(SecretEvidenceError):
        harness.outcome_service.record(
            strategy.strategy_id, execution.execution_id, evidence={"note": "api_key: sk-abcdefghijklmnop"}
        )
