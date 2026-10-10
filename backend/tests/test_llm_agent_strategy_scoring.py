import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_effectiveness import LLMAgentStrategyOutcomeService
from backend.agent_strategy_library import LLMAgentStrategyService, UnknownAgentStrategyError
from backend.agent_strategy_scoring import LLMAgentStrategyScore, LLMAgentStrategyScorer
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
    """One shared tool-calling pipeline that can run both successful and
    failing plans, wired to real Commit #1/#3 strategy/outcome services --
    the same minimal shape backend/tests/test_llm_agent_strategy_effectiveness.py
    already uses, extended with a Commit #4 LLMAgentStrategyScorer."""

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


def test_baseline_score():
    harness = Harness()
    strategy = harness.strategy()

    result = harness.scorer.score(strategy.strategy_id, now=NOW)

    assert isinstance(result, LLMAgentStrategyScore)
    assert result.strategy_id == strategy.strategy_id
    assert result.evidence_count == 0
    assert result.score == 0.5
    assert result.confidence == 0.0
    assert result.scored_at == NOW


def test_repeated_success():
    harness = Harness()
    strategy = harness.strategy()

    for _ in range(5):
        harness.outcome(strategy.strategy_id, tool_name="lookup")

    result = harness.scorer.score(strategy.strategy_id, now=NOW)

    assert result.evidence_count == 5
    assert result.succeeded_count == 5
    assert result.failed_count == 0
    assert result.score == pytest.approx(1.0, abs=1e-3)
    assert result.confidence > 0.9


def test_repeated_failure():
    harness = Harness()
    strategy = harness.strategy()

    for _ in range(5):
        harness.outcome(strategy.strategy_id, tool_name="broken-lookup")

    result = harness.scorer.score(strategy.strategy_id, now=NOW)

    assert result.evidence_count == 5
    assert result.succeeded_count == 0
    assert result.failed_count == 5
    assert result.score == pytest.approx(0.0, abs=1e-3)
    assert result.confidence > 0.9


def test_mixed_outcomes_preserve_contradiction():
    harness = Harness()
    strategy = harness.strategy()

    for _ in range(2):
        harness.outcome(strategy.strategy_id, tool_name="lookup")
    for _ in range(2):
        harness.outcome(strategy.strategy_id, tool_name="broken-lookup")

    result = harness.scorer.score(strategy.strategy_id, now=NOW)

    assert result.evidence_count == 4
    assert result.succeeded_count == 2
    assert result.failed_count == 2
    assert result.score == pytest.approx(0.5, abs=1e-3)
    # contradictory evidence pulls confidence down relative to a
    # same-volume, unanimous history
    unanimous_confidence = 1.0 - 0.5 ** 4
    assert result.confidence < unanimous_confidence

    # both sides of the contradiction are still fully on record, never
    # dropped or collapsed to a single verdict
    outcomes = harness.outcome_service.list_for_strategy(strategy.strategy_id)
    assert len(outcomes) == 4


def test_insufficient_evidence_caps_confidence():
    harness = Harness()
    strategy = harness.strategy()
    harness.outcome(strategy.strategy_id, tool_name="lookup")

    result = harness.scorer.score(strategy.strategy_id, now=NOW)

    assert result.evidence_count == 1
    # one successful execution alone drives score to the extreme, but
    # must never earn more than modest confidence
    assert result.score == 1.0
    assert result.confidence <= 0.5


def test_recency_behavior():
    harness = Harness()
    strategy = harness.strategy()

    old_success = harness.outcome(strategy.strategy_id, tool_name="lookup")
    recent_failure = harness.outcome(strategy.strategy_id, tool_name="broken-lookup")

    backdated_success = dataclasses.replace(old_success, created_at=NOW - timedelta(days=365))
    harness.outcome_service.store.save(backdated_success)
    dated_failure = dataclasses.replace(recent_failure, created_at=NOW)
    harness.outcome_service.store.save(dated_failure)

    result = harness.scorer.score(strategy.strategy_id, now=NOW)

    # the ancient success barely weighs in; the recent failure dominates
    assert result.evidence_count == 2
    assert result.succeeded_count == 1
    assert result.failed_count == 1
    assert result.score < 0.05


def test_deterministic_scoring():
    harness = Harness()
    strategy = harness.strategy()
    harness.outcome(strategy.strategy_id, tool_name="lookup")
    harness.outcome(strategy.strategy_id, tool_name="broken-lookup")

    first = harness.scorer.score(strategy.strategy_id, now=NOW)
    second = harness.scorer.score(strategy.strategy_id, now=NOW)

    assert first == second


def test_batch_scoring():
    harness = Harness()
    strategy_a = harness.strategy(scope_id="notebook-1", name="strategy-a")
    strategy_b = harness.strategy(scope_id="notebook-1", name="strategy-b")
    harness.outcome(strategy_a.strategy_id, tool_name="lookup")
    harness.outcome(strategy_b.strategy_id, tool_name="broken-lookup")

    individual_a = harness.scorer.score(strategy_a.strategy_id, now=NOW)
    individual_b = harness.scorer.score(strategy_b.strategy_id, now=NOW)

    batch = harness.scorer.score_many([strategy_a.strategy_id, strategy_b.strategy_id], now=NOW)

    assert batch == [individual_a, individual_b]


def test_scoring_does_not_mutate_strategy():
    harness = Harness()
    strategy = harness.strategy()
    harness.outcome(strategy.strategy_id, tool_name="lookup")

    before = harness.strategy_service.get(strategy.strategy_id)
    harness.scorer.score(strategy.strategy_id, now=NOW)
    after = harness.strategy_service.get(strategy.strategy_id)

    assert before == after


def test_missing_strategy():
    harness = Harness()

    with pytest.raises(UnknownAgentStrategyError):
        harness.scorer.score("missing-strategy", now=NOW)
