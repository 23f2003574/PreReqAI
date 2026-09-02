from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_feedback import LLMAgentMemoryFeedbackService
from backend.agent_memory_promotion import (
    CANDIDATE,
    DEPRECATED,
    TRUSTED,
    InsufficientEvidenceError,
    InvalidPromotionTransitionError,
    LLMAgentMemoryPromoter,
)
from backend.agent_memory_quality_assessment import LLMAgentMemoryQualityAssessor
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.tool_control import LLMToolExecutionControlService
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
            LLMToolPermissionPolicy(policy_id="allow-lookup", tool_name="lookup", subject=ANY_SUBJECT, allowed=True)
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
        self.feedback_service = LLMAgentMemoryFeedbackService(self.memory_service, self.plan_execution)
        self.assessor = LLMAgentMemoryQualityAssessor(self.memory_service, self.feedback_service)
        self.promoter = LLMAgentMemoryPromoter(self.memory_service, self.assessor)
        self._counter = 0

    def execute(self):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        self.store.add(_plan(plan_id, "lookup"))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == SUCCEEDED
        return execution

    def record_memory(self, scope_id: str, content: str, backdate: datetime = None):
        execution = self.execute()
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

    def make_qualifying(self, memory_id):
        """Enough consistent positive feedback to cross both trusted thresholds."""
        self.give_feedback(memory_id, "successful", rating=1.0)
        self.give_feedback(memory_id, "successful", rating=1.0)


def test_candidate_lifecycle():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)

    assert harness.promoter.status_for(memory.memory_id) == CANDIDATE
    assert harness.promoter.history(memory.memory_id) == []


def test_qualifying_memory_promotion():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    harness.make_qualifying(memory.memory_id)

    decision = harness.promoter.evaluate(memory.memory_id, now=NOW)
    assert decision.eligible is True
    assert decision.recommended_status == TRUSTED

    record = harness.promoter.promote(memory.memory_id, now=NOW)

    assert record.status == TRUSTED
    assert record.memory_id == memory.memory_id
    assert harness.promoter.status_for(memory.memory_id) == TRUSTED
    assert harness.promoter.history(memory.memory_id) == [record]


def test_insufficient_evidence():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    # only the memory's own outcome as evidence -- confidence stays at 0.5,
    # below MIN_TRUSTED_CONFIDENCE

    decision = harness.promoter.evaluate(memory.memory_id, now=NOW)
    assert decision.eligible is False

    with pytest.raises(InsufficientEvidenceError):
        harness.promoter.promote(memory.memory_id, now=NOW)

    assert harness.promoter.status_for(memory.memory_id) == CANDIDATE


def test_negative_contradictory_evidence():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    harness.give_feedback(memory.memory_id, "incorrect", rating=-1.0)
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)

    decision = harness.promoter.evaluate(memory.memory_id, now=NOW)
    assert decision.eligible is False

    with pytest.raises(InsufficientEvidenceError):
        harness.promoter.promote(memory.memory_id, now=NOW)


def test_deprecation():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)

    record = harness.promoter.deprecate(memory.memory_id, "found to give wrong tuning advice", now=NOW)

    assert record.status == DEPRECATED
    assert record.reason == "found to give wrong tuning advice"
    assert harness.promoter.status_for(memory.memory_id) == DEPRECATED

    with pytest.raises(ValueError):
        harness.promoter.deprecate(memory.memory_id, "", now=NOW)


def test_provenance_preservation():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    harness.make_qualifying(memory.memory_id)
    harness.promoter.promote(memory.memory_id, now=NOW)

    unchanged = harness.memory_service.get(memory.memory_id)
    assert unchanged.content == "gradient descent basics"
    assert unchanged.execution_id == memory.execution_id
    assert unchanged.outcome == memory.outcome
    assert unchanged.created_at == memory.created_at

    other = harness.record_memory("notebook-1", "linear regression basics", backdate=NOW)
    harness.promoter.deprecate(other.memory_id, "superseded", now=NOW)
    still_there = harness.memory_service.get(other.memory_id)
    assert still_there.content == "linear regression basics"


def test_invalid_transitions():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    harness.make_qualifying(memory.memory_id)

    harness.promoter.deprecate(memory.memory_id, "turned out to be wrong", now=NOW)
    assert harness.promoter.status_for(memory.memory_id) == DEPRECATED

    with pytest.raises(InvalidPromotionTransitionError):
        harness.promoter.promote(memory.memory_id, now=NOW)

    # deprecation itself is always allowed again, e.g. to update the reason
    record = harness.promoter.deprecate(memory.memory_id, "confirmed wrong a second time", now=NOW)
    assert record.status == DEPRECATED
    assert harness.promoter.status_for(memory.memory_id) == DEPRECATED


def test_scope_isolation():
    harness = Harness()
    trusted_in_1 = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    harness.make_qualifying(trusted_in_1.memory_id)
    harness.promoter.promote(trusted_in_1.memory_id, now=NOW)

    candidate_in_1 = harness.record_memory("notebook-1", "another fact", backdate=NOW)
    trusted_in_2 = harness.record_memory("notebook-2", "gradient descent basics", backdate=NOW)
    harness.make_qualifying(trusted_in_2.memory_id)
    harness.promoter.promote(trusted_in_2.memory_id, now=NOW)

    scope_1_trusted = harness.promoter.list_for_scope("notebook-1", status=TRUSTED)
    assert [m.memory_id for m in scope_1_trusted] == [trusted_in_1.memory_id]

    scope_1_all = harness.promoter.list_for_scope("notebook-1")
    assert {m.memory_id for m in scope_1_all} == {trusted_in_1.memory_id, candidate_in_1.memory_id}

    # a notebook-1 query never surfaces notebook-2's trusted memory
    assert trusted_in_2.memory_id not in {m.memory_id for m in scope_1_trusted}
