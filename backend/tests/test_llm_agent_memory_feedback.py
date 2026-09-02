from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService, UnknownAgentMemoryError
from backend.agent_memory_feedback import (
    InvalidFeedbackTypeError,
    InvalidRatingError,
    LLMAgentMemoryFeedbackService,
    SecretFeedbackCommentError,
    UnknownAgentMemoryFeedbackError,
)
from backend.agent_plan_execution import LLMAgentPlanExecutionService, UnknownAgentPlanExecutionError
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
        self._counter = 0

    def execute(self, succeed: bool = True):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        self.store.add(_plan(plan_id, "lookup"))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == SUCCEEDED
        return execution

    def record_memory(self, scope_id: str, content: str, memory_type: str = "strategy"):
        execution = self.execute()
        return self.memory_service.record(
            execution.execution_id, {"scope_id": scope_id, "memory_type": memory_type, "content": content}
        )


def test_valid_feedback():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    later_execution = harness.execute()

    feedback = harness.feedback_service.record(
        memory.memory_id,
        {"execution_id": later_execution.execution_id, "feedback_type": "useful", "rating": 0.8, "comment": "helped a lot"},
    )

    assert feedback.memory_id == memory.memory_id
    assert feedback.execution_id == later_execution.execution_id
    assert feedback.feedback_type == "useful"
    assert feedback.rating == 0.8
    assert feedback.comment == "helped a lot"
    assert feedback.feedback_id is not None
    assert feedback.created_at is not None

    fetched = harness.feedback_service.get(feedback.feedback_id)
    assert fetched.feedback_id == feedback.feedback_id


def test_missing_memory():
    harness = Harness()
    execution = harness.execute()

    with pytest.raises(UnknownAgentMemoryError):
        harness.feedback_service.record(
            "missing-memory-id", {"execution_id": execution.execution_id, "feedback_type": "useful"}
        )


def test_missing_execution():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")

    with pytest.raises(UnknownAgentPlanExecutionError):
        harness.feedback_service.record(
            memory.memory_id, {"execution_id": "missing-execution-id", "feedback_type": "useful"}
        )


def test_multiple_feedback_records_preserve_history():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    exec_1 = harness.execute()
    exec_2 = harness.execute()

    first = harness.feedback_service.record(
        memory.memory_id, {"execution_id": exec_1.execution_id, "feedback_type": "useful"}
    )
    second = harness.feedback_service.record(
        memory.memory_id, {"execution_id": exec_2.execution_id, "feedback_type": "incorrect", "comment": "wrong this time"}
    )

    history = harness.feedback_service.list_for_memory(memory.memory_id)
    assert [f.feedback_id for f in history] == [first.feedback_id, second.feedback_id]
    # nothing was overwritten -- the earlier judgment is still exactly as recorded
    assert harness.feedback_service.get(first.feedback_id).feedback_type == "useful"
    assert harness.feedback_service.get(second.feedback_id).feedback_type == "incorrect"


def test_scope_isolation():
    harness = Harness()
    memory_a = harness.record_memory("notebook-1", "gradient descent basics")
    memory_b = harness.record_memory("notebook-2", "gradient descent basics")
    exec_a = harness.execute()
    exec_b = harness.execute()

    harness.feedback_service.record(memory_a.memory_id, {"execution_id": exec_a.execution_id, "feedback_type": "useful"})
    harness.feedback_service.record(memory_b.memory_id, {"execution_id": exec_b.execution_id, "feedback_type": "not_useful"})

    assert memory_a.scope_id != memory_b.scope_id

    feedback_for_a = harness.feedback_service.list_for_memory(memory_a.memory_id)
    feedback_for_b = harness.feedback_service.list_for_memory(memory_b.memory_id)

    assert [f.feedback_type for f in feedback_for_a] == ["useful"]
    assert [f.feedback_type for f in feedback_for_b] == ["not_useful"]
    assert all(f.memory_id == memory_a.memory_id for f in feedback_for_a)


def test_invalid_feedback_type():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    execution = harness.execute()

    with pytest.raises(InvalidFeedbackTypeError):
        harness.feedback_service.record(
            memory.memory_id, {"execution_id": execution.execution_id, "feedback_type": "not-a-real-type"}
        )


def test_invalid_rating():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    execution = harness.execute()

    with pytest.raises(InvalidRatingError):
        harness.feedback_service.record(
            memory.memory_id, {"execution_id": execution.execution_id, "feedback_type": "useful", "rating": 2.5}
        )

    with pytest.raises(InvalidRatingError):
        harness.feedback_service.record(
            memory.memory_id, {"execution_id": execution.execution_id, "feedback_type": "useful", "rating": "high"}
        )


def test_sensitive_data_handling():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    execution = harness.execute()

    with pytest.raises(SecretFeedbackCommentError):
        harness.feedback_service.record(
            memory.memory_id,
            {
                "execution_id": execution.execution_id,
                "feedback_type": "incorrect",
                "comment": "the tool leaked api_key: sk-abcdefghijklmnop",
            },
        )

    assert harness.feedback_service.list_for_memory(memory.memory_id) == []


def test_retrieval_by_memory():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    other_memory = harness.record_memory("notebook-1", "completely different fact")
    execution = harness.execute()

    harness.feedback_service.record(memory.memory_id, {"execution_id": execution.execution_id, "feedback_type": "successful"})

    assert [f.feedback_type for f in harness.feedback_service.list_for_memory(memory.memory_id)] == ["successful"]
    assert harness.feedback_service.list_for_memory(other_memory.memory_id) == []


def test_missing_feedback():
    harness = Harness()
    with pytest.raises(UnknownAgentMemoryFeedbackError):
        harness.feedback_service.get("missing-feedback-id")


def test_feedback_never_mutates_memory():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    execution = harness.execute()

    harness.feedback_service.record(
        memory.memory_id, {"execution_id": execution.execution_id, "feedback_type": "incorrect", "rating": -1.0}
    )

    unchanged = harness.memory_service.get(memory.memory_id)
    assert unchanged.content == "gradient descent basics"
    assert unchanged.outcome == SUCCEEDED
