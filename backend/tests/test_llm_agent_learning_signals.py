from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_learning_signals import (
    FAILED_STRATEGY,
    INCORRECT_KNOWLEDGE,
    REPEATED_FAILURE,
    REPEATED_SUCCESS,
    SUCCESSFUL_STRATEGY,
    USEFUL_KNOWLEDGE,
    LLMAgentLearningSignalExtractor,
)
from backend.agent_memory_consolidation import LLMAgentMemoryConsolidator
from backend.agent_memory_feedback import LLMAgentMemoryFeedbackService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import FAILED, REJECTED, SUCCEEDED, LLMToolExecutionService
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
        registry.register("broken_lookup", "Tool broken_lookup", SCHEMA)

        invocation = LLMToolInvocationService(registry)
        permissions = LLMToolPermissionService(registry, invocation)
        for tool_name in ("lookup", "broken_lookup"):
            permissions.register(
                LLMToolPermissionPolicy(
                    policy_id=f"allow-{tool_name}", tool_name=tool_name, subject=ANY_SUBJECT, allowed=True
                )
            )

        execution = LLMToolExecutionService(registry, permissions)
        execution.bind("lookup", ok)
        execution.bind("broken_lookup", always_fails)

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

        self.validation_service = LLMAgentPlanValidationService(
            self.store, registry, permissions, invocation_service=invocation
        )
        step_execution = LLMAgentExecutionService(self.store, self.validation_service, orchestrator)
        self.plan_execution = LLMAgentPlanExecutionService(self.store, self.validation_service, step_execution)
        self.memory_service = LLMAgentMemoryService(self.plan_execution)
        self.feedback_service = LLMAgentMemoryFeedbackService(self.memory_service, self.plan_execution)
        self.consolidator = LLMAgentMemoryConsolidator(self.memory_service)
        self.extractor = LLMAgentLearningSignalExtractor(
            self.plan_execution, self.memory_service, self.feedback_service
        )
        self._counter = 0

    def execute(self, succeed: bool = True):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        tool_name = "lookup" if succeed else "broken_lookup"
        self.store.add(_plan(plan_id, tool_name))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == (SUCCEEDED if succeed else FAILED)
        return execution

    def execute_rejected(self):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        self.store.add(_plan(plan_id, "unregistered_tool"))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == REJECTED
        return execution

    def record_memory(self, scope_id: str, content: str, succeed: bool = True):
        execution = self.execute(succeed=succeed)
        return self.memory_service.record(
            execution.execution_id, {"scope_id": scope_id, "memory_type": "strategy", "content": content}
        )

    def give_feedback(self, memory_id, feedback_type, rating=None):
        execution = self.execute()
        return self.feedback_service.record(
            memory_id, {"execution_id": execution.execution_id, "feedback_type": feedback_type, "rating": rating}
        )


def test_successful_execution_signal():
    harness = Harness()
    execution = harness.execute(succeed=True)

    signals = harness.extractor.extract(execution.execution_id, now=NOW)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == SUCCESSFUL_STRATEGY
    assert signal.execution_id == execution.execution_id
    assert signal.memory_id is None
    assert signal.value == 1.0
    assert signal.evidence["status"] == SUCCEEDED


def test_failed_execution_signal():
    harness = Harness()
    execution = harness.execute(succeed=False)

    signals = harness.extractor.extract(execution.execution_id, now=NOW)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type == FAILED_STRATEGY
    assert signal.value == 0.0
    assert signal.evidence["status"] == FAILED


def test_feedback_derived_signals():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    useful = harness.give_feedback(memory.memory_id, "useful", rating=0.8)
    incorrect = harness.give_feedback(memory.memory_id, "incorrect", rating=-0.9)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)

    by_type = {}
    for signal in signals:
        by_type.setdefault(signal.signal_type, []).append(signal)

    assert len(by_type[USEFUL_KNOWLEDGE]) == 1
    assert by_type[USEFUL_KNOWLEDGE][0].evidence["feedback_id"] == useful.feedback_id
    assert len(by_type[INCORRECT_KNOWLEDGE]) == 1
    assert by_type[INCORRECT_KNOWLEDGE][0].evidence["feedback_id"] == incorrect.feedback_id
    assert all(signal.memory_id == memory.memory_id for signal in signals)


def test_repeated_outcomes_from_feedback():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "useful", rating=1.0)
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)

    repeated = [s for s in signals if s.signal_type == REPEATED_SUCCESS]
    assert len(repeated) == 1
    assert repeated[0].evidence["count"] == 2


def test_repeated_outcomes_from_consolidation():
    harness = Harness()
    a = harness.record_memory("notebook-1", "gradient descent optimizes the loss function")
    b = harness.record_memory("notebook-1", "gradient descent optimizes the loss function with tuning")
    consolidated = harness.consolidator.consolidate([a, b])

    signals = harness.extractor.extract_for_memory(consolidated.memory_id, now=NOW)

    repeated = [s for s in signals if s.signal_type == REPEATED_SUCCESS and s.evidence["source"] == "consolidation"]
    assert len(repeated) == 1
    assert set(repeated[0].evidence["source_memory_ids"]) == {a.memory_id, b.memory_id}


def test_contradictory_evidence_preserved():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "useful", rating=1.0)
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)
    harness.give_feedback(memory.memory_id, "incorrect", rating=-1.0)
    harness.give_feedback(memory.memory_id, "failed", rating=-1.0)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    types_present = {s.signal_type for s in signals}

    # both directions of individual feedback signal survive side by side...
    assert USEFUL_KNOWLEDGE in types_present
    assert INCORRECT_KNOWLEDGE in types_present
    # ...and once each side reaches the repeat threshold, both repeated
    # signals are reported too -- neither collapses into a single verdict.
    assert REPEATED_SUCCESS in types_present
    assert REPEATED_FAILURE in types_present


def test_provenance():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    feedback = harness.give_feedback(memory.memory_id, "useful", rating=0.5)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)

    outcome_signal = next(s for s in signals if s.evidence.get("source") == "execution")
    assert outcome_signal.memory_id == memory.memory_id
    assert outcome_signal.evidence["execution_id"] == memory.execution_id

    feedback_signal = next(s for s in signals if s.evidence.get("source") == "feedback")
    assert feedback_signal.evidence["feedback_id"] == feedback.feedback_id
    assert feedback_signal.execution_id == feedback.execution_id

    # extraction never mutates the underlying memory or its feedback
    assert harness.memory_service.get(memory.memory_id).content == "gradient descent basics"
    assert harness.feedback_service.get(feedback.feedback_id).feedback_type == "useful"


def test_scope_isolation():
    harness = Harness()
    memory_a = harness.record_memory("notebook-1", "gradient descent basics")
    memory_b = harness.record_memory("notebook-2", "gradient descent basics")
    harness.give_feedback(memory_a.memory_id, "useful", rating=1.0)
    harness.give_feedback(memory_b.memory_id, "incorrect", rating=-1.0)

    signals_a = harness.extractor.extract_for_memory(memory_a.memory_id, now=NOW)
    signals_b = harness.extractor.extract_for_memory(memory_b.memory_id, now=NOW)

    assert all(s.memory_id == memory_a.memory_id for s in signals_a)
    assert all(s.memory_id == memory_b.memory_id for s in signals_b)
    assert {s.signal_type for s in signals_a} & {INCORRECT_KNOWLEDGE} == set()
    assert {s.signal_type for s in signals_b} & {USEFUL_KNOWLEDGE} == set()


def test_empty_evidence():
    harness = Harness()

    rejected = harness.execute_rejected()
    assert harness.extractor.extract(rejected.execution_id, now=NOW) == []

    memory = harness.record_memory("notebook-1", "gradient descent basics")
    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    assert len(signals) == 1
    assert signals[0].evidence["source"] == "execution"
    assert signals[0].memory_id == memory.memory_id


def test_deterministic_extraction():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "useful", rating=0.6)
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)

    def _content(signals):
        return sorted(
            (s.execution_id, s.memory_id, s.signal_type, s.value, tuple(sorted(s.evidence.items(), key=str)))
            for s in signals
        )

    first = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    second = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    assert _content(first) == _content(second)

    execution = harness.execute(succeed=True)
    first_exec = harness.extractor.extract(execution.execution_id, now=NOW)
    second_exec = harness.extractor.extract(execution.execution_id, now=NOW)
    assert _content(first_exec) == _content(second_exec)
