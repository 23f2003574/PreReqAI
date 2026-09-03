from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_decision_audit import LLMAgentStrategyDecisionAuditService
from backend.agent_strategy_effectiveness import LLMAgentStrategyOutcomeService
from backend.agent_strategy_feedback import LLMAgentStrategyFeedbackService
from backend.agent_strategy_learning_integration import LLMAgentStrategyLearningIntegration
from backend.agent_strategy_learning_orchestration import PROCESSED, LLMAgentStrategyLearningOrchestrator
from backend.agent_strategy_library import LLMAgentStrategyService
from backend.agent_strategy_lifecycle import LLMAgentStrategyLifecycleEvaluator
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


class BrokenOrchestrator:
    """A stand-in for Commit #12's own orchestrator that always raises --
    test-only failure injection to prove a learning failure this severe
    still can never reach or change an execution's own result."""

    def process_execution(self, execution_id, now=None):
        raise RuntimeError("the learning pipeline blew up")


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
        self.feedback_service = LLMAgentStrategyFeedbackService(
            self.plan_execution, self.usage_service, self.outcome_service
        )
        self.scorer = LLMAgentStrategyScorer(self.strategy_service, self.outcome_service)
        self.lifecycle_evaluator = LLMAgentStrategyLifecycleEvaluator(self.strategy_service, self.scorer)
        self.audit_service = LLMAgentStrategyDecisionAuditService(self.strategy_service)
        self.learning_orchestrator = LLMAgentStrategyLearningOrchestrator(
            self.plan_execution, self.feedback_service, self.scorer, self.lifecycle_evaluator, self.audit_service
        )
        self.integration = LLMAgentStrategyLearningIntegration(self.plan_execution, self.learning_orchestrator)

        self._plan_counter = 0

    def run_directly(self, tool_name="lookup", plan_id=None):
        """Runs a plan through the real, un-integrated execution service --
        used to record usage against a real execution_id before learning
        is separately triggered via on_execution_completed()."""
        if plan_id is None:
            self._plan_counter += 1
            plan_id = f"plan-{self._plan_counter}"
        self.store.add(_plan(plan_id, tool_name))
        return self.plan_execution.execute(plan_id, "user:ada")

    def memory(self, scope_id="notebook-1", tool_name="lookup", content="call lookup with topic first"):
        execution = self.run_directly(tool_name=tool_name)
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


def test_successful_execution_integration():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run_directly(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    result = harness.integration.on_execution_completed(execution.execution_id, now=NOW)

    assert result.status == PROCESSED
    assert result.outcomes[0].result == SUCCEEDED
    assert result.lifecycle_decisions[0].strategy_id == strategy.strategy_id
    assert result.audit_decisions[0].strategy_id == strategy.strategy_id
    assert harness.integration.learning_result_for(execution.execution_id) is result


def test_failed_execution_integration():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run_directly(tool_name="broken-lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    result = harness.integration.on_execution_completed(execution.execution_id, now=NOW)

    assert result.status == PROCESSED
    assert result.outcomes[0].result == FAILED


def test_duplicate_completion_idempotency():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run_directly(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    first = harness.integration.on_execution_completed(execution.execution_id, now=NOW)
    assert first is not None

    second = harness.integration.on_execution_completed(execution.execution_id, now=NOW)
    assert second is None

    # the first result is still exactly what learning_result_for() returns
    assert harness.integration.learning_result_for(execution.execution_id) is first
    # nothing grew in the underlying trails from the repeat call
    assert len(harness.audit_service.list_for_execution(execution.execution_id)) == 1
    assert len(harness.outcome_service.list_for_strategy(strategy.strategy_id)) == 1


def test_learning_failure_isolation():
    harness = Harness()
    broken_integration = LLMAgentStrategyLearningIntegration(harness.plan_execution, BrokenOrchestrator())

    harness.store.add(_plan("plan-broken", "lookup"))
    execution = broken_integration.execute("plan-broken", "user:ada")

    assert execution.status == SUCCEEDED
    assert broken_integration.learning_result_for(execution.execution_id) is None

    # a repeat call is also a safe no-op, not a re-raise
    assert broken_integration.on_execution_completed(execution.execution_id, now=NOW) is None


def test_no_strategy_execution():
    harness = Harness()
    harness.store.add(_plan("plan-unused", "lookup"))
    execution = harness.integration.execute("plan-unused", "user:ada", now=NOW)

    assert execution.status == SUCCEEDED
    result = harness.integration.learning_result_for(execution.execution_id)
    assert result.status == PROCESSED
    assert result.outcomes == []
    assert result.lifecycle_decisions == []
    assert result.audit_decisions == []


def test_provenance_and_scope_preservation():
    harness = Harness()
    strategy_a = harness.strategy(scope_id="notebook-1", name="strategy-a")
    strategy_b = harness.strategy(scope_id="notebook-2", name="strategy-b")

    execution = harness.run_directly(tool_name="lookup")
    harness.use(strategy_a.strategy_id, execution.execution_id)
    harness.use(strategy_b.strategy_id, execution.execution_id)

    result = harness.integration.on_execution_completed(execution.execution_id, now=NOW)

    assert {o.strategy_id for o in result.outcomes} == {strategy_a.strategy_id, strategy_b.strategy_id}
    assert {d.strategy_id for d in result.lifecycle_decisions} == {strategy_a.strategy_id, strategy_b.strategy_id}
    assert {d.strategy_id for d in result.audit_decisions} == {strategy_a.strategy_id, strategy_b.strategy_id}

    # each strategy's own provenance/scope stays exactly its own
    audit_a = harness.audit_service.list_for_strategy(strategy_a.strategy_id)
    audit_b = harness.audit_service.list_for_strategy(strategy_b.strategy_id)
    assert [r.strategy_id for r in audit_a] == [strategy_a.strategy_id]
    assert [r.strategy_id for r in audit_b] == [strategy_b.strategy_id]
    assert harness.strategy_service.get(strategy_a.strategy_id).scope_id == "notebook-1"
    assert harness.strategy_service.get(strategy_b.strategy_id).scope_id == "notebook-2"


def test_existing_lifecycle_regression():
    harness = Harness()
    # no strategy or usage at all -- integrated execution should behave
    # identically to calling the real execution service directly

    harness.store.add(_plan("plan-direct", "lookup"))
    direct = harness.plan_execution.execute("plan-direct", "user:ada")

    another_harness = Harness()
    another_harness.store.add(_plan("plan-direct", "lookup"))
    integrated = another_harness.integration.execute("plan-direct", "user:ada")

    assert integrated.status == direct.status
    assert integrated.completed_steps == direct.completed_steps
    assert integrated.failed_step == direct.failed_step


def test_running_execution_is_not_processed():
    harness = Harness()
    captured = {}

    def before_step(execution_id, step_id):
        captured["result"] = harness.integration.on_execution_completed(execution_id, now=NOW)
        return True

    harness.store.add(_plan("plan-incomplete", "lookup"))
    harness.plan_execution.execute("plan-incomplete", "user:ada", before_step=before_step)

    assert captured["result"] is None
