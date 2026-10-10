from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_learning_signals import LLMAgentLearningSignalExtractor
from backend.agent_memory_feedback import LLMAgentMemoryFeedbackService
from backend.agent_memory_learning_integration import LLMAgentMemoryLearningIntegration
from backend.agent_memory_learning_orchestration import (
    PROCESSED,
    SKIPPED,
    LLMAgentMemoryLearningOrchestrator,
)
from backend.agent_memory_learning_updates import LLMAgentMemoryLearningUpdater
from backend.agent_memory_promotion import TRUSTED, LLMAgentMemoryPromoter
from backend.agent_memory_quality_assessment import LLMAgentMemoryQualityAssessor
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


class BrokenOrchestrator:
    def process_execution(self, execution_id, now=None):
        raise RuntimeError("learning blew up")

    def process_memory(self, memory_id, now=None):
        raise RuntimeError("learning blew up")


class Harness:
    def __init__(self):
        self.store = MultiPlanStore()

        self.registry = LLMToolRegistryService()
        self.registry.register("lookup", "Tool lookup", SCHEMA)
        self.registry.register("broken_lookup", "Tool broken_lookup", SCHEMA)

        invocation = LLMToolInvocationService(self.registry)
        permissions = LLMToolPermissionService(self.registry, invocation)
        for tool_name in ("lookup", "broken_lookup"):
            permissions.register(
                LLMToolPermissionPolicy(
                    policy_id=f"allow-{tool_name}", tool_name=tool_name, subject=ANY_SUBJECT, allowed=True
                )
            )

        execution = LLMToolExecutionService(self.registry, permissions)
        execution.bind("lookup", ok)
        execution.bind("broken_lookup", always_fails)

        idempotency = LLMToolIdempotencyService(execution, permissions)
        control = LLMToolExecutionControlService(execution, idempotency)
        retry = LLMToolRetryService(
            control, execution, LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
            sleeper=lambda seconds: None, idempotency_service=idempotency,
        )
        results = LLMToolResultService()
        orchestrator_stack = LLMToolCallingOrchestrationService(
            invocation_service=invocation, permission_service=permissions, execution_service=execution,
            result_service=results, idempotency_service=idempotency, control_service=control,
            retry_service=retry,
        )

        self.validation_service = LLMAgentPlanValidationService(
            self.store, self.registry, permissions, invocation_service=invocation
        )
        step_execution = LLMAgentExecutionService(self.store, self.validation_service, orchestrator_stack)
        self.plan_execution = LLMAgentPlanExecutionService(self.store, self.validation_service, step_execution)
        self.memory_service = LLMAgentMemoryService(self.plan_execution)
        self.feedback_service = LLMAgentMemoryFeedbackService(self.memory_service, self.plan_execution)
        self.extractor = LLMAgentLearningSignalExtractor(
            self.plan_execution, self.memory_service, self.feedback_service
        )
        self.quality_assessor = LLMAgentMemoryQualityAssessor(self.memory_service, self.feedback_service)
        self.promoter = LLMAgentMemoryPromoter(self.memory_service, self.quality_assessor)
        self.updater = LLMAgentMemoryLearningUpdater(
            self.memory_service, self.extractor, quality_assessor=self.quality_assessor, promoter=self.promoter
        )
        self.learning_orchestrator = LLMAgentMemoryLearningOrchestrator(
            self.plan_execution, self.memory_service, self.extractor, self.updater,
            self.quality_assessor, self.promoter,
        )
        self.integration = LLMAgentMemoryLearningIntegration(self.plan_execution, self.learning_orchestrator)
        self._counter = 0

    def next_plan_id(self):
        self._counter += 1
        return f"plan-{self._counter}"

    def record_memory(self, scope_id: str, content: str):
        plan_id = self.next_plan_id()
        self.store.add(_plan(plan_id, "lookup"))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == SUCCEEDED
        return self.memory_service.record(
            execution.execution_id, {"scope_id": scope_id, "memory_type": "strategy", "content": content}
        )

    def give_feedback(self, memory_id, feedback_type, rating=None):
        plan_id = self.next_plan_id()
        self.store.add(_plan(plan_id, "lookup"))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        return self.feedback_service.record(
            memory_id, {"execution_id": execution.execution_id, "feedback_type": feedback_type, "rating": rating}
        )


def test_successful_execution_triggers_learning():
    harness = Harness()
    plan_id = harness.next_plan_id()
    harness.store.add(_plan(plan_id, "lookup"))

    execution = harness.integration.execute(plan_id, "user:ada", now=NOW)

    assert execution.status == SUCCEEDED
    result = harness.integration.learning_result_for(execution.execution_id)
    assert result is not None
    assert result.status == PROCESSED
    assert result.execution_id == execution.execution_id


def test_failed_execution_triggers_eligible_learning():
    harness = Harness()
    plan_id = harness.next_plan_id()
    harness.store.add(_plan(plan_id, "broken_lookup"))

    execution = harness.integration.execute(plan_id, "user:ada", now=NOW)

    assert execution.status == FAILED
    result = harness.integration.learning_result_for(execution.execution_id)
    assert result is not None
    assert result.status == PROCESSED
    assert any(s.signal_type == "failed_strategy" for s in result.signals)


def test_terminal_state_enforcement():
    harness = Harness()
    captured = {}

    def before_step(execution_id, step_id):
        captured["execution_id"] = execution_id
        captured["result"] = harness.integration.on_execution_completed(execution_id, now=NOW)
        return True

    plan_id = harness.next_plan_id()
    harness.store.add(_plan(plan_id, "lookup"))
    harness.plan_execution.execute(plan_id, "user:ada", before_step=before_step)

    # the execution was still RUNNING when on_execution_completed() was called
    assert captured["result"] is None
    assert harness.integration.learning_result_for(captured["execution_id"]) is None


def test_duplicate_completion_does_not_duplicate_learning():
    harness = Harness()
    plan_id = harness.next_plan_id()
    harness.store.add(_plan(plan_id, "lookup"))
    execution = harness.plan_execution.execute(plan_id, "user:ada")

    first = harness.integration.on_execution_completed(execution.execution_id, now=NOW)
    second = harness.integration.on_execution_completed(execution.execution_id, now=NOW)

    assert first is not None
    assert second is None
    # the first result is still there, untouched
    assert harness.integration.learning_result_for(execution.execution_id) is first


def test_learning_failure_does_not_corrupt_execution_result():
    harness = Harness()
    broken_integration = LLMAgentMemoryLearningIntegration(harness.plan_execution, BrokenOrchestrator())

    plan_id = harness.next_plan_id()
    harness.store.add(_plan(plan_id, "lookup"))
    execution = broken_integration.execute(plan_id, "user:ada", now=NOW)

    assert execution.status == SUCCEEDED
    assert execution.completed_steps == ["step-1"]
    assert broken_integration.learning_result_for(execution.execution_id) is None
    # the execution record itself is unaffected -- still readable, still SUCCEEDED
    assert harness.plan_execution.get(execution.execution_id).status == SUCCEEDED


def test_scope_provenance_preservation():
    harness = Harness()
    memory_a = harness.record_memory("notebook-1", "gradient descent basics")
    memory_b = harness.record_memory("notebook-2", "gradient descent basics")
    harness.give_feedback(memory_a.memory_id, "successful", rating=1.0)
    harness.give_feedback(memory_a.memory_id, "successful", rating=1.0)

    plan_id = harness.next_plan_id()
    harness.store.add(_plan(plan_id, "lookup"))
    execution = harness.integration.execute(plan_id, "user:ada", memory_id=memory_a.memory_id, now=NOW)

    result = harness.integration.learning_result_for(execution.execution_id)
    assert result.memory_id == memory_a.memory_id
    assert result.status == PROCESSED
    assert harness.promoter.status_for(memory_a.memory_id) == TRUSTED
    # scope-2's own memory is completely untouched
    assert harness.promoter.status_for(memory_b.memory_id) != TRUSTED
    assert harness.updater.metadata_for(memory_b.memory_id).supporting_evidence_count == 0

    identities = {ref[1] for ref in result.metadata.evidence_refs}
    assert memory_a.execution_id in identities


def test_existing_execution_lifecycle_remains_valid():
    harness = Harness()

    plan_id_direct = harness.next_plan_id()
    harness.store.add(_plan(plan_id_direct, "lookup"))
    direct_execution = harness.plan_execution.execute(plan_id_direct, "user:ada")

    plan_id_wrapped = harness.next_plan_id()
    harness.store.add(_plan(plan_id_wrapped, "lookup"))
    wrapped_execution = harness.integration.execute(plan_id_wrapped, "user:ada", now=NOW)

    assert wrapped_execution.status == direct_execution.status
    assert wrapped_execution.completed_steps == direct_execution.completed_steps
    assert wrapped_execution.failed_step == direct_execution.failed_step


def test_no_op_when_execution_contains_no_learnable_evidence():
    harness = Harness()
    plan_id = harness.next_plan_id()
    harness.store.add(_plan(plan_id, "unregistered_tool"))

    execution = harness.integration.execute(plan_id, "user:ada", now=NOW)

    assert execution.status == REJECTED
    assert harness.integration.learning_result_for(execution.execution_id) is None
