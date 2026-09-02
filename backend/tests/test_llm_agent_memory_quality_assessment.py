from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_consolidation import LLMAgentMemoryConsolidator
from backend.agent_memory_feedback import LLMAgentMemoryFeedbackService
from backend.agent_memory_quality_assessment import LLMAgentMemoryQuality, LLMAgentMemoryQualityAssessor
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

        validation_service = LLMAgentPlanValidationService(
            self.store, registry, permissions, invocation_service=invocation
        )
        step_execution = LLMAgentExecutionService(self.store, validation_service, orchestrator)
        self.plan_execution = LLMAgentPlanExecutionService(self.store, validation_service, step_execution)
        self.memory_service = LLMAgentMemoryService(self.plan_execution)
        self.feedback_service = LLMAgentMemoryFeedbackService(self.memory_service, self.plan_execution)
        self.consolidator = LLMAgentMemoryConsolidator(self.memory_service)
        self.assessor = LLMAgentMemoryQualityAssessor(self.memory_service, self.feedback_service)
        self._counter = 0

    def execute(self, succeed: bool = True):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        tool_name = "lookup" if succeed else "broken_lookup"
        self.store.add(_plan(plan_id, tool_name))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == (SUCCEEDED if succeed else FAILED)
        return execution

    def record_memory(self, scope_id: str, content: str, succeed: bool = True, backdate: datetime = None):
        execution = self.execute(succeed=succeed)
        memory = self.memory_service.record(
            execution.execution_id, {"scope_id": scope_id, "memory_type": "strategy", "content": content}
        )
        if backdate is not None:
            memory.created_at = backdate
            self.memory_service.store.save(memory)
        return memory

    def give_feedback(self, memory_id, feedback_type, rating=None):
        execution = self.execute()
        return self.feedback_service.record(
            memory_id, {"execution_id": execution.execution_id, "feedback_type": feedback_type, "rating": rating}
        )


def test_baseline_memory_quality():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)

    quality = harness.assessor.assess(memory.memory_id, now=NOW)

    assert isinstance(quality, LLMAgentMemoryQuality)
    assert quality.memory_id == memory.memory_id
    assert quality.evidence_count == 1
    assert quality.quality_score == 1.0
    # a single execution alone earns only modest confidence
    assert quality.confidence == 0.5
    assert "own outcome=SUCCEEDED" in quality.assessment_reason


def test_successful_evidence_increases_quality():
    harness = Harness()
    # a memory whose own execution FAILED starts with a low quality_score;
    # strong positive feedback from later reuse should still lift it.
    memory = harness.record_memory("notebook-1", "gradient descent basics", succeed=False, backdate=NOW)
    baseline = harness.assessor.assess(memory.memory_id, now=NOW)

    harness.give_feedback(memory.memory_id, "successful", rating=1.0)
    harness.give_feedback(memory.memory_id, "useful", rating=1.0)

    boosted = harness.assessor.assess(memory.memory_id, now=NOW)

    assert boosted.quality_score > baseline.quality_score
    assert boosted.confidence > baseline.confidence
    assert boosted.evidence_count == 3


def test_negative_feedback_lowers_quality():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    baseline = harness.assessor.assess(memory.memory_id, now=NOW)

    harness.give_feedback(memory.memory_id, "incorrect", rating=-1.0)
    harness.give_feedback(memory.memory_id, "failed", rating=-0.8)

    degraded = harness.assessor.assess(memory.memory_id, now=NOW)

    assert degraded.quality_score < baseline.quality_score


def test_contradictory_evidence_reduces_confidence():
    harness = Harness()
    agreeing = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    contradicted = harness.record_memory("notebook-1", "linear regression basics", backdate=NOW)

    harness.give_feedback(agreeing.memory_id, "successful", rating=1.0)
    harness.give_feedback(agreeing.memory_id, "useful", rating=0.9)

    harness.give_feedback(contradicted.memory_id, "successful", rating=1.0)
    harness.give_feedback(contradicted.memory_id, "incorrect", rating=-1.0)

    agreeing_result = harness.assessor.assess(agreeing.memory_id, now=NOW)
    contradicted_result = harness.assessor.assess(contradicted.memory_id, now=NOW)

    # same evidence_count, but disagreement costs confidence
    assert agreeing_result.evidence_count == contradicted_result.evidence_count
    assert contradicted_result.confidence < agreeing_result.confidence


def test_repeated_evidence_increases_confidence():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)

    results = []
    for _ in range(4):
        results.append(harness.assessor.assess(memory.memory_id, now=NOW))
        harness.give_feedback(memory.memory_id, "successful", rating=1.0)

    confidences = [result.confidence for result in results]
    assert confidences == sorted(confidences)
    assert confidences[0] < confidences[-1]


def test_stale_old_memory_behavior():
    harness = Harness()
    fresh = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    old = harness.record_memory("notebook-1", "linear regression basics", backdate=NOW - timedelta(days=365))

    fresh_quality = harness.assessor.assess(fresh.memory_id, now=NOW)
    old_quality = harness.assessor.assess(old.memory_id, now=NOW)

    assert old_quality.confidence < fresh_quality.confidence
    # staleness never destroys confidence outright
    assert old_quality.confidence > 0.0
    # quality_score (what the evidence says) is untouched by age -- only confidence is
    assert old_quality.quality_score == fresh_quality.quality_score


def test_deterministic_assessment():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    harness.give_feedback(memory.memory_id, "useful", rating=0.5)

    first = harness.assessor.assess(memory.memory_id, now=NOW)
    second = harness.assessor.assess(memory.memory_id, now=NOW)

    assert first == second

    # assessing never mutates the underlying memory
    assert harness.memory_service.get(memory.memory_id).content == "gradient descent basics"


def test_batch_assessment():
    harness = Harness()
    a = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    b = harness.record_memory("notebook-1", "linear regression basics", succeed=False, backdate=NOW)
    harness.give_feedback(a.memory_id, "successful", rating=1.0)

    batch = harness.assessor.assess_batch([a.memory_id, b.memory_id], now=NOW)
    individually = [harness.assessor.assess(a.memory_id, now=NOW), harness.assessor.assess(b.memory_id, now=NOW)]

    assert batch == individually
    assert [q.memory_id for q in batch] == [a.memory_id, b.memory_id]


def test_consolidation_history_evidence():
    harness = Harness()
    a = harness.record_memory("notebook-1", "gradient descent optimizes the loss function", backdate=NOW)
    b = harness.record_memory(
        "notebook-1", "gradient descent optimizes the loss function with tuning", backdate=NOW
    )

    consolidated = harness.consolidator.consolidate([a, b])
    quality = harness.assessor.assess(consolidated.memory_id, now=NOW)

    assert quality.evidence_count == 1 + 2  # own outcome + 2 consolidated sources
    assert "consolidated source" in quality.assessment_reason
