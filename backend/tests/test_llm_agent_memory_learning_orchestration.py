from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_learning_signals import LLMAgentLearningSignalExtractor
from backend.agent_memory_learning_orchestration import (
    FAILED,
    PROCESSED,
    SKIPPED,
    LLMAgentMemoryLearningOrchestrator,
)
from backend.agent_memory_learning_updates import LLMAgentMemoryLearningUpdater
from backend.agent_memory_feedback import LLMAgentMemoryFeedbackService
from backend.agent_memory_promotion import TRUSTED, LLMAgentMemoryPromoter
from backend.agent_memory_quality_assessment import LLMAgentMemoryQualityAssessor
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import REJECTED, SUCCEEDED, LLMToolExecutionService
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


class BrokenExtractor:
    def extract_for_memory(self, memory_id, now=None):
        raise RuntimeError("signal extraction blew up")

    def extract(self, execution_id, now=None):
        raise RuntimeError("signal extraction blew up")


class BrokenUpdater:
    def __init__(self, real_updater):
        self._real = real_updater

    def apply_signals(self, memory_id, signals, now=None):
        raise RuntimeError("memory update blew up")

    def metadata_for(self, memory_id):
        return self._real.metadata_for(memory_id)

    def update_from_execution(self, execution_id, now=None):
        raise RuntimeError("memory update blew up")


class Harness:
    def __init__(self):
        self.store = MultiPlanStore()

        self.registry = LLMToolRegistryService()
        self.registry.register("lookup", "Tool lookup", SCHEMA)

        invocation = LLMToolInvocationService(self.registry)
        permissions = LLMToolPermissionService(self.registry, invocation)
        permissions.register(
            LLMToolPermissionPolicy(policy_id="allow-lookup", tool_name="lookup", subject=ANY_SUBJECT, allowed=True)
        )

        execution = LLMToolExecutionService(self.registry, permissions)
        execution.bind("lookup", ok)

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
        self.orchestrator = LLMAgentMemoryLearningOrchestrator(
            self.plan_execution, self.memory_service, self.extractor, self.updater,
            self.quality_assessor, self.promoter,
        )
        self._counter = 0

    def execute(self):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        self.store.add(_plan(plan_id, "lookup"))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == SUCCEEDED
        return execution

    def execute_rejected(self):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        self.store.add(_plan(plan_id, "unregistered_tool"))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == REJECTED
        return execution

    def record_memory(self, scope_id: str, content: str):
        execution = self.execute()
        return self.memory_service.record(
            execution.execution_id, {"scope_id": scope_id, "memory_type": "strategy", "content": content}
        )

    def give_feedback(self, memory_id, feedback_type, rating=None):
        execution = self.execute()
        return self.feedback_service.record(
            memory_id, {"execution_id": execution.execution_id, "feedback_type": feedback_type, "rating": rating}
        )


def test_complete_learning_pipeline():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)

    result = harness.orchestrator.process_memory(memory.memory_id, now=NOW)

    assert result.status == PROCESSED
    assert result.memory_id == memory.memory_id
    assert result.execution_id == memory.execution_id
    assert len(result.signals) >= 3
    assert result.metadata.supporting_evidence_count >= 3
    assert result.quality.quality_score == 1.0
    assert result.promotion_decision.eligible is True
    assert result.promotion_record is not None
    assert result.promotion_record.status == TRUSTED
    assert harness.promoter.status_for(memory.memory_id) == TRUSTED

    step_names = [op["step"] for op in result.operations]
    assert step_names == ["read_memory", "extract_signals", "apply_signals", "assess_quality", "promotion"]
    assert all(op["outcome"] in ("ok", "promoted") for op in result.operations)


def test_incomplete_execution_ignored():
    harness = Harness()
    captured = {}

    def before_step(execution_id, step_id):
        captured["execution_id"] = execution_id
        result = harness.orchestrator.process_execution(execution_id, now=NOW)
        captured["result"] = result
        return True

    harness.store.add(_plan("plan-running", "lookup"))
    harness.plan_execution.execute("plan-running", "user:ada", before_step=before_step)

    assert captured["result"].status == SKIPPED
    assert captured["result"].execution_id == captured["execution_id"]
    assert captured["result"].signals == []


def test_idempotent_reprocessing():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)

    first = harness.orchestrator.process_memory(memory.memory_id, now=NOW)
    second = harness.orchestrator.process_memory(memory.memory_id, now=NOW)

    assert first.metadata.supporting_evidence_count == second.metadata.supporting_evidence_count
    assert first.metadata.evidence_refs == second.metadata.evidence_refs
    assert second.promotion_record is None  # already trusted -- not re-promoted
    assert [op["outcome"] for op in second.operations if op["step"] == "promotion"] == ["already_trusted"]
    assert len(harness.promoter.history(memory.memory_id)) == 1


def test_signal_extraction_failure():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    broken = LLMAgentMemoryLearningOrchestrator(
        harness.plan_execution, harness.memory_service, BrokenExtractor(), harness.updater,
        harness.quality_assessor, harness.promoter,
    )

    result = broken.process_memory(memory.memory_id, now=NOW)

    assert result.status == FAILED
    assert result.signals == []
    assert result.metadata is None
    assert result.quality is None
    assert [op["outcome"] for op in result.operations if op["step"] == "extract_signals"] == ["error"]

    # nothing downstream was touched
    assert harness.updater.metadata_for(memory.memory_id).supporting_evidence_count == 0
    assert harness.promoter.status_for(memory.memory_id) != TRUSTED
    assert harness.memory_service.get(memory.memory_id).content == "gradient descent basics"


def test_memory_update_failure():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)
    broken = LLMAgentMemoryLearningOrchestrator(
        harness.plan_execution, harness.memory_service, harness.extractor, BrokenUpdater(harness.updater),
        harness.quality_assessor, harness.promoter,
    )

    result = broken.process_memory(memory.memory_id, now=NOW)

    assert result.status == FAILED
    assert len(result.signals) > 0
    assert result.metadata is None
    assert result.quality is None
    assert result.promotion_decision is None
    assert [op["outcome"] for op in result.operations if op["step"] == "apply_signals"] == ["error"]

    assert harness.promoter.status_for(memory.memory_id) != TRUSTED
    assert harness.memory_service.get(memory.memory_id).content == "gradient descent basics"


def test_quality_promotion_integration():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)

    result = harness.orchestrator.process_memory(memory.memory_id, now=NOW)

    assert result.quality == harness.quality_assessor.assess(memory.memory_id, now=NOW)
    # decision reflects status *before* this call's own promotion took effect
    assert result.promotion_decision.eligible is True
    assert result.promotion_decision.recommended_status == TRUSTED
    assert result.promotion_record.status == TRUSTED
    # ...and the promoter's own state now agrees
    assert harness.promoter.status_for(memory.memory_id) == TRUSTED


def test_provenance_preservation():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    feedback = harness.give_feedback(memory.memory_id, "useful", rating=0.7)

    result = harness.orchestrator.process_memory(memory.memory_id, now=NOW)

    feedback_ids_in_signals = {
        s.evidence.get("feedback_id") for s in result.signals if s.evidence.get("source") == "feedback"
    }
    assert feedback.feedback_id in feedback_ids_in_signals

    identities = {ref[1] for ref in result.metadata.evidence_refs}
    assert feedback.feedback_id in identities
    assert memory.execution_id in identities
    assert result.execution_id == memory.execution_id


def test_scope_isolation():
    harness = Harness()
    memory_a = harness.record_memory("notebook-1", "gradient descent basics")
    memory_b = harness.record_memory("notebook-2", "gradient descent basics")
    harness.give_feedback(memory_a.memory_id, "successful", rating=1.0)
    harness.give_feedback(memory_a.memory_id, "successful", rating=1.0)

    harness.orchestrator.process_memory(memory_a.memory_id, now=NOW)

    assert harness.promoter.status_for(memory_a.memory_id) == TRUSTED
    assert harness.promoter.status_for(memory_b.memory_id) != TRUSTED
    assert harness.updater.metadata_for(memory_b.memory_id).supporting_evidence_count == 0


def test_no_op_when_no_learning_evidence_exists():
    harness = Harness()
    rejected = harness.execute_rejected()

    result = harness.orchestrator.process_execution(rejected.execution_id, now=NOW)

    assert result.status == PROCESSED
    assert result.signals == []
    assert [op["step"] for op in result.operations] == ["read_execution", "extract_signals", "apply_signals"]
