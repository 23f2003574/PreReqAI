from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_strategy_decision_audit import LEARNED, LLMAgentStrategyDecisionAuditService
from backend.agent_strategy_effectiveness import LLMAgentStrategyOutcomeService
from backend.agent_strategy_feedback import LLMAgentStrategyFeedbackService
from backend.agent_strategy_library import ACTIVE, LLMAgentStrategyService
from backend.agent_strategy_lifecycle import TRUSTED, LLMAgentStrategyLifecycleEvaluator
from backend.agent_strategy_learning_orchestration import (
    FAILED,
    PROCESSED,
    SKIPPED,
    LLMAgentStrategyLearningOrchestrator,
)
from backend.agent_strategy_scoring import LLMAgentStrategyScorer
from backend.agent_strategy_usage import LLMAgentStrategyUsageService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import FAILED as TOOL_FAILED
from backend.llm.tool_execution import SUCCEEDED, LLMToolExecutionService
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


class FlakyScorer:
    """Wraps a real Commit #4 LLMAgentStrategyScorer but raises for one
    chosen strategy_id -- test-only failure injection, so the real
    orchestrator can be exercised against a genuine per-strategy error
    without touching any real service's own code."""

    def __init__(self, real_scorer, fail_strategy_id):
        self._real = real_scorer
        self._fail_strategy_id = fail_strategy_id

    def score(self, strategy_id, now=None):
        if strategy_id == self._fail_strategy_id:
            raise RuntimeError("scoring blew up")
        return self._real.score(strategy_id, now=now)


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


def test_complete_learning_flow():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    result = harness.learning_orchestrator.process_execution(execution.execution_id, now=NOW)

    assert result.status == PROCESSED
    assert result.execution_id == execution.execution_id
    assert [o.strategy_id for o in result.outcomes] == [strategy.strategy_id]
    assert result.outcomes[0].result == SUCCEEDED
    assert [s.strategy_id for s in result.scores] == [strategy.strategy_id]
    assert [d.strategy_id for d in result.lifecycle_decisions] == [strategy.strategy_id]
    assert [d.strategy_id for d in result.audit_decisions] == [strategy.strategy_id]
    assert result.audit_decisions[0].decision_type == LEARNED

    step_names = [op["step"] for op in result.operations]
    assert "read_execution" in step_names
    assert "record_outcomes" in step_names
    assert f"score:{strategy.strategy_id}" in step_names
    assert f"lifecycle:{strategy.strategy_id}" in step_names
    assert f"audit:{strategy.strategy_id}" in step_names
    assert all(op["outcome"] == "ok" for op in result.operations)


def test_failed_execution():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="broken-lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    result = harness.learning_orchestrator.process_execution(execution.execution_id, now=NOW)

    assert result.status == PROCESSED
    assert result.outcomes[0].result == TOOL_FAILED
    assert result.lifecycle_decisions[0].failed_count == 1
    assert result.lifecycle_decisions[0].succeeded_count == 0


def test_no_strategies_used():
    harness = Harness()
    execution = harness.run(tool_name="lookup")
    # no usage recorded at all

    result = harness.learning_orchestrator.process_execution(execution.execution_id, now=NOW)

    assert result.status == PROCESSED
    assert result.outcomes == []
    assert result.scores == []
    assert result.lifecycle_decisions == []
    assert result.audit_decisions == []
    assert any(op["step"] == "learning" and op["outcome"] == "skipped" for op in result.operations)


def test_duplicate_processing():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    first = harness.learning_orchestrator.process_execution(execution.execution_id, now=NOW)
    assert first.status == PROCESSED

    second = harness.learning_orchestrator.process_execution(execution.execution_id, now=NOW)
    assert second.status == SKIPPED
    assert second.audit_decisions == []
    assert second.lifecycle_decisions == []

    # nothing grew from the second call
    assert len(harness.audit_service.list_for_execution(execution.execution_id)) == 1
    assert len(harness.lifecycle_evaluator.store.list_for_strategy(strategy.strategy_id)) == 1
    assert len(harness.outcome_service.list_for_strategy(strategy.strategy_id)) == 1


def test_outcome_scoring_integration():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    result = harness.learning_orchestrator.process_execution(execution.execution_id, now=NOW)

    # the score in the result is the exact one Commit #4's own scorer
    # would independently compute from the same, now-persisted evidence
    independent_score = harness.scorer.score(strategy.strategy_id, now=NOW)
    assert result.scores[0] == independent_score


def test_lifecycle_integration():
    harness = Harness()
    strategy = harness.strategy()

    for _ in range(3):
        execution = harness.run(tool_name="lookup")
        harness.use(strategy.strategy_id, execution.execution_id)
        result = harness.learning_orchestrator.process_execution(execution.execution_id, now=NOW)

    assert result.lifecycle_decisions[0].status == TRUSTED
    assert result.lifecycle_decisions[0].previous_status in (ACTIVE, TRUSTED)


def test_audit_integration():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    result = harness.learning_orchestrator.process_execution(execution.execution_id, now=NOW)

    audit_records = harness.audit_service.list_for_strategy(strategy.strategy_id)
    assert len(audit_records) == 1
    record = audit_records[0]
    assert record.decision_type == LEARNED
    assert record.decision == result.lifecycle_decisions[0].status
    assert record.reason == result.lifecycle_decisions[0].reason
    assert record.score == result.lifecycle_decisions[0].score
    assert record.evidence["outcome_id"] == result.outcomes[0].outcome_id


def test_failure_isolation():
    harness = Harness()
    strategy_ok = harness.strategy(name="strategy-ok")
    strategy_broken = harness.strategy(name="strategy-broken")

    execution = harness.run(tool_name="lookup")
    harness.use(strategy_ok.strategy_id, execution.execution_id)
    harness.use(strategy_broken.strategy_id, execution.execution_id)

    flaky_scorer = FlakyScorer(harness.scorer, fail_strategy_id=strategy_broken.strategy_id)
    orchestrator = LLMAgentStrategyLearningOrchestrator(
        harness.plan_execution, harness.feedback_service, flaky_scorer,
        harness.lifecycle_evaluator, harness.audit_service,
    )

    result = orchestrator.process_execution(execution.execution_id, now=NOW)

    assert result.status == PROCESSED
    # both strategies got their outcome recorded ...
    assert {o.strategy_id for o in result.outcomes} == {strategy_ok.strategy_id, strategy_broken.strategy_id}
    # ... but only the healthy one made it through scoring/lifecycle/audit
    assert [s.strategy_id for s in result.scores] == [strategy_ok.strategy_id]
    assert [d.strategy_id for d in result.lifecycle_decisions] == [strategy_ok.strategy_id]
    assert [d.strategy_id for d in result.audit_decisions] == [strategy_ok.strategy_id]

    error_steps = [op for op in result.operations if op["outcome"] == "error"]
    assert len(error_steps) == 1
    assert error_steps[0]["step"] == f"score:{strategy_broken.strategy_id}"

    # the broken strategy's outcome is still safely on record, even
    # though learning from it failed this time
    assert len(harness.outcome_service.list_for_strategy(strategy_broken.strategy_id)) == 1


def test_learning_never_alters_execution():
    harness = Harness()
    strategy = harness.strategy()
    execution = harness.run(tool_name="lookup")
    harness.use(strategy.strategy_id, execution.execution_id)

    before = harness.plan_execution.get(execution.execution_id)
    harness.learning_orchestrator.process_execution(execution.execution_id, now=NOW)
    after = harness.plan_execution.get(execution.execution_id)

    assert before == after


def test_running_execution_is_skipped():
    harness = Harness()
    strategy = harness.strategy()
    captured = {}

    def before_step(execution_id, step_id):
        captured["execution_id"] = execution_id
        result = harness.learning_orchestrator.process_execution(execution_id, now=NOW)
        captured["result"] = result
        return True

    harness.store.add(_plan("plan-incomplete", "lookup"))
    harness.plan_execution.execute("plan-incomplete", "user:ada", before_step=before_step)

    assert captured["result"].status == SKIPPED
