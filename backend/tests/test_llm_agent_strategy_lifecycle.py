from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_effectiveness import LLMAgentStrategyOutcomeService
from backend.agent_strategy_library import ACTIVE, LLMAgentStrategyService, UnknownAgentStrategyError
from backend.agent_strategy_lifecycle import (
    DEPRECATED,
    TRUSTED,
    LLMAgentStrategyLifecycleDecision,
    LLMAgentStrategyLifecycleEvaluator,
)
from backend.agent_strategy_scoring import LLMAgentStrategyScorer
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
        self.evaluator = LLMAgentStrategyLifecycleEvaluator(self.strategy_service, self.scorer)

        self._plan_counter = 0

    def run(self, tool_name="lookup", plan_id=None):
        if plan_id is None:
            self._plan_counter += 1
            plan_id = f"plan-{self._plan_counter}"
        self.store.add(_plan(plan_id, tool_name))
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

    def outcome(self, strategy_id, tool_name="lookup"):
        execution = self.run(tool_name=tool_name)
        return self.outcome_service.record(strategy_id, execution.execution_id)

    def supported(self, strategy_id, successes=0, failures=0):
        for _ in range(successes):
            self.outcome(strategy_id, tool_name="lookup")
        for _ in range(failures):
            self.outcome(strategy_id, tool_name="broken-lookup")


def test_promotion_with_strong_evidence():
    harness = Harness()
    strategy = harness.strategy()
    harness.supported(strategy.strategy_id, successes=3)

    decision = harness.evaluator.evaluate(strategy.strategy_id, now=NOW)

    assert isinstance(decision, LLMAgentStrategyLifecycleDecision)
    assert decision.strategy_id == strategy.strategy_id
    assert decision.previous_status == ACTIVE
    assert decision.status == TRUSTED
    assert decision.evidence_count == 3
    assert decision.succeeded_count == 3
    assert decision.failed_count == 0
    assert decision.reason


def test_insufficient_evidence_stays_active():
    harness = Harness()
    strategy = harness.strategy()
    harness.supported(strategy.strategy_id, successes=1)

    decision = harness.evaluator.evaluate(strategy.strategy_id, now=NOW)

    # a single success drives Commit #4's own score to the extreme, but
    # confidence alone can never justify promotion off one outcome
    assert decision.score == 1.0
    assert decision.status == ACTIVE


def test_repeated_failures_trigger_deprecation():
    harness = Harness()
    strategy = harness.strategy()
    harness.supported(strategy.strategy_id, failures=3)

    decision = harness.evaluator.evaluate(strategy.strategy_id, now=NOW)

    assert decision.status == DEPRECATED
    assert decision.succeeded_count == 0
    assert decision.failed_count == 3


def test_mixed_outcomes_stay_represented_and_active():
    harness = Harness()
    strategy = harness.strategy()
    harness.supported(strategy.strategy_id, successes=2, failures=2)

    decision = harness.evaluator.evaluate(strategy.strategy_id, now=NOW)

    # contradictory evidence never gets collapsed away -- both counts
    # stay visible in the decision itself
    assert decision.succeeded_count == 2
    assert decision.failed_count == 2
    # too little agreement to justify either a trusted or deprecated verdict
    assert decision.status == ACTIVE


def test_invalid_transition_deprecated_never_auto_reverts():
    harness = Harness()
    strategy = harness.strategy()
    harness.supported(strategy.strategy_id, failures=3)

    deprecated = harness.evaluator.evaluate(strategy.strategy_id, now=NOW)
    assert deprecated.status == DEPRECATED

    # strong new evidence accumulates afterwards ...
    harness.supported(strategy.strategy_id, successes=5)
    still_deprecated = harness.evaluator.evaluate(strategy.strategy_id, now=NOW)

    # ... but deprecation is never automatically reversed by re-evaluation
    assert still_deprecated.status == DEPRECATED
    assert still_deprecated.previous_status == DEPRECATED
    assert "not automatic" in still_deprecated.reason


def test_history_and_provenance_preservation():
    harness = Harness()
    strategy = harness.strategy()

    harness.supported(strategy.strategy_id, successes=1)
    first = harness.evaluator.evaluate(strategy.strategy_id, now=NOW)

    harness.supported(strategy.strategy_id, successes=2)
    second = harness.evaluator.evaluate(strategy.strategy_id, now=NOW)

    history = harness.evaluator.store.list_for_strategy(strategy.strategy_id)

    assert [item.decision_id for item in history] == [first.decision_id, second.decision_id]
    assert first.status == ACTIVE
    assert first.evidence_count == 1
    assert second.status == TRUSTED
    assert second.evidence_count == 3
    # neither decision is ever mutated by a later one
    assert history[0].evidence_count == 1
    assert history[1].evidence_count == 3

    # the underlying Commit #1 strategy and Commit #3 outcomes are
    # untouched by any of this
    assert harness.strategy_service.get(strategy.strategy_id).status == ACTIVE
    assert len(harness.outcome_service.list_for_strategy(strategy.strategy_id)) == 3


def test_batch_evaluation():
    harness = Harness()
    strategy_a = harness.strategy(scope_id="notebook-1", name="strategy-a")
    harness.supported(strategy_a.strategy_id, successes=3)
    strategy_b = harness.strategy(scope_id="notebook-1", name="strategy-b")
    harness.supported(strategy_b.strategy_id, failures=3)

    individual_a = harness.evaluator.evaluate(strategy_a.strategy_id, now=NOW)
    individual_b = harness.evaluator.evaluate(strategy_b.strategy_id, now=NOW)

    # a fresh evaluator/store so the batch call starts from the same
    # blank history the individual calls did
    fresh = LLMAgentStrategyLifecycleEvaluator(harness.strategy_service, harness.scorer)
    batch = fresh.evaluate_many([strategy_a.strategy_id, strategy_b.strategy_id], now=NOW)

    assert [item.status for item in batch] == [individual_a.status, individual_b.status]
    assert batch[0].strategy_id == strategy_a.strategy_id
    assert batch[1].strategy_id == strategy_b.strategy_id


def test_missing_strategy():
    harness = Harness()

    with pytest.raises(UnknownAgentStrategyError):
        harness.evaluator.evaluate("missing-strategy", now=NOW)
