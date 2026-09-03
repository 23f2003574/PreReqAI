from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService, UnknownAgentPlanExecutionError
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_effectiveness import LLMAgentStrategyOutcomeService
from backend.agent_strategy_feedback import LLMAgentStrategyFeedbackService
from backend.agent_strategy_library import LLMAgentStrategyService
from backend.agent_strategy_scoring import LLMAgentStrategyScorer
from backend.agent_strategy_usage import LLMAgentStrategyUsageService
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
        self.usage_service = LLMAgentStrategyUsageService(self.strategy_service, self.plan_execution)
        self.scorer = LLMAgentStrategyScorer(self.strategy_service, self.outcome_service)
        self.feedback_service = LLMAgentStrategyFeedbackService(
            self.plan_execution, self.usage_service, self.outcome_service
        )

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

    def use(self, strategy_id, execution_id, selection_score=0.8, applied=True):
        return self.usage_service.record(strategy_id, execution_id, selection_score=selection_score, applied=applied)


def test_successful_strategy_feedback():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    outcomes = harness.feedback_service.process_execution(execution.execution_id)

    assert len(outcomes) == 1
    assert outcomes[0].strategy_id == strategy.strategy_id
    assert outcomes[0].execution_id == execution.execution_id
    assert outcomes[0].result == SUCCEEDED

    stored = harness.outcome_service.list_for_strategy(strategy.strategy_id)
    assert [item.outcome_id for item in stored] == [outcomes[0].outcome_id]


def test_failed_strategy_feedback():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="broken-lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    outcomes = harness.feedback_service.process_execution(execution.execution_id)

    assert len(outcomes) == 1
    assert outcomes[0].result == FAILED


def test_unused_strategy_ignored():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id, applied=False)

    outcomes = harness.feedback_service.process_execution(execution.execution_id)

    assert outcomes == []
    assert harness.outcome_service.list_for_strategy(strategy.strategy_id) == []


def test_duplicate_processing_is_idempotent():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    first = harness.feedback_service.process_execution(execution.execution_id)
    second = harness.feedback_service.process_execution(execution.execution_id)

    assert [item.outcome_id for item in first] == [item.outcome_id for item in second]
    assert len(harness.outcome_service.list_for_strategy(strategy.strategy_id)) == 1


def test_multiple_strategies_in_one_execution():
    harness = Harness()
    strategy_1 = harness.strategy(name="strategy-1")
    strategy_2 = harness.strategy(name="strategy-2")
    execution = harness.run(tool_name="lookup")
    harness.use(strategy_1.strategy_id, execution.execution_id)
    harness.use(strategy_2.strategy_id, execution.execution_id)
    # a third, unapplied strategy on the same execution should be skipped
    strategy_3 = harness.strategy(name="strategy-3")
    harness.use(strategy_3.strategy_id, execution.execution_id, applied=False)

    outcomes = harness.feedback_service.process_execution(execution.execution_id)

    ids = {item.strategy_id for item in outcomes}
    assert ids == {strategy_1.strategy_id, strategy_2.strategy_id}


def test_scope_isolation():
    harness = Harness()
    strategy_a = harness.strategy(scope_id="notebook-1", name="strategy-a")
    strategy_b = harness.strategy(scope_id="notebook-2", name="strategy-b")

    execution = harness.run(tool_name="lookup")
    harness.use(strategy_a.strategy_id, execution.execution_id)
    harness.use(strategy_b.strategy_id, execution.execution_id)

    outcomes = harness.feedback_service.process_execution(execution.execution_id)

    ids = {item.strategy_id for item in outcomes}
    assert ids == {strategy_a.strategy_id, strategy_b.strategy_id}

    # each strategy's own evidence stays exactly its own -- no leakage
    # across the scope boundary despite sharing one execution
    assert [item.strategy_id for item in harness.outcome_service.list_for_strategy(strategy_a.strategy_id)] == [
        strategy_a.strategy_id
    ]
    assert [item.strategy_id for item in harness.outcome_service.list_for_strategy(strategy_b.strategy_id)] == [
        strategy_b.strategy_id
    ]


def test_scoring_sees_new_evidence():
    harness = Harness()
    strategy = harness.strategy()

    before = harness.scorer.score(strategy.strategy_id, now=NOW)
    assert before.evidence_count == 0

    execution = harness.run(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)
    harness.feedback_service.process_execution(execution.execution_id)

    after = harness.scorer.score(strategy.strategy_id, now=NOW)
    assert after.evidence_count == 1
    assert after.succeeded_count == 1
    assert after.score > before.score


def test_processing_does_not_alter_execution():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    before = harness.plan_execution.get(execution.execution_id)
    harness.feedback_service.process_execution(execution.execution_id)
    after = harness.plan_execution.get(execution.execution_id)

    assert before == after


def test_missing_execution():
    harness = Harness()

    with pytest.raises(UnknownAgentPlanExecutionError):
        harness.feedback_service.process_execution("missing-execution")
