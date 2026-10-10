from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_learning_signals import LLMAgentLearningSignal, LLMAgentLearningSignalExtractor
from backend.agent_memory_feedback import LLMAgentMemoryFeedbackService
from backend.agent_memory_learning_updates import (
    LLMAgentMemoryLearningUpdater,
    MismatchedSignalError,
)
from backend.agent_memory_promotion import LLMAgentMemoryPromoter
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
        self.extractor = LLMAgentLearningSignalExtractor(
            self.plan_execution, self.memory_service, self.feedback_service
        )
        self.quality_assessor = LLMAgentMemoryQualityAssessor(self.memory_service, self.feedback_service)
        self.promoter = LLMAgentMemoryPromoter(self.memory_service, self.quality_assessor)
        self.updater = LLMAgentMemoryLearningUpdater(
            self.memory_service, self.extractor, quality_assessor=self.quality_assessor, promoter=self.promoter
        )
        self._counter = 0

    def execute(self):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        self.store.add(_plan(plan_id, "lookup"))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == SUCCEEDED
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


def test_successful_learning_update():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "useful", rating=1.0)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    result = harness.updater.apply_signals(memory.memory_id, signals, now=NOW)

    assert result.memory_id == memory.memory_id
    metadata = harness.updater.metadata_for(memory.memory_id)
    # the memory's own SUCCEEDED origin + one favorable feedback record
    assert metadata.supporting_evidence_count == 2
    assert metadata.contradicting_evidence_count == 0
    assert metadata.successful_use_count == 1
    assert metadata.failed_use_count == 0
    assert metadata.last_updated_at == NOW


def test_failure_negative_update():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "incorrect", rating=-1.0)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    harness.updater.apply_signals(memory.memory_id, signals, now=NOW)

    metadata = harness.updater.metadata_for(memory.memory_id)
    assert metadata.contradicting_evidence_count == 1
    assert metadata.failed_use_count == 1
    assert metadata.successful_use_count == 0


def test_repeated_signal_idempotency():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "useful", rating=1.0)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    harness.updater.apply_signals(memory.memory_id, signals, now=NOW)
    first = harness.updater.metadata_for(memory.memory_id)

    # reapplying the exact same signals -- whether the same list object or
    # a freshly re-extracted, equivalent one -- must not double-count
    harness.updater.apply_signals(memory.memory_id, signals, now=NOW)
    again_same_list = harness.updater.metadata_for(memory.memory_id)

    fresh_signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    harness.updater.apply_signals(memory.memory_id, fresh_signals, now=NOW)
    again_fresh_list = harness.updater.metadata_for(memory.memory_id)

    assert again_same_list.supporting_evidence_count == first.supporting_evidence_count
    assert again_same_list.successful_use_count == first.successful_use_count
    assert again_fresh_list.supporting_evidence_count == first.supporting_evidence_count
    assert again_fresh_list.successful_use_count == first.successful_use_count


def test_contradictory_evidence_remains_visible():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "useful", rating=1.0)
    harness.give_feedback(memory.memory_id, "incorrect", rating=-1.0)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    harness.updater.apply_signals(memory.memory_id, signals, now=NOW)

    metadata = harness.updater.metadata_for(memory.memory_id)
    assert metadata.supporting_evidence_count > 0
    assert metadata.contradicting_evidence_count > 0
    assert metadata.successful_use_count == 1
    assert metadata.failed_use_count == 1


def test_provenance():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    other_memory = harness.record_memory("notebook-1", "linear regression basics")
    feedback = harness.give_feedback(memory.memory_id, "useful", rating=1.0)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    harness.updater.apply_signals(memory.memory_id, signals, now=NOW)

    metadata = harness.updater.metadata_for(memory.memory_id)
    identities = {ref[1] for ref in metadata.evidence_refs}
    assert feedback.feedback_id in identities
    assert memory.execution_id in identities

    # a signal that does not actually belong to this memory is refused,
    # not silently folded into its tally
    foreign_signal = LLMAgentLearningSignal(
        execution_id="some-other-execution",
        signal_type="useful_knowledge",
        value=1.0,
        evidence={"source": "feedback", "feedback_id": "not-really-there", "feedback_type": "useful", "rating": 1.0},
        memory_id=other_memory.memory_id,
    )
    with pytest.raises(MismatchedSignalError):
        harness.updater.apply_signals(memory.memory_id, [foreign_signal], now=NOW)


def test_scope_isolation():
    harness = Harness()
    memory_a = harness.record_memory("notebook-1", "gradient descent basics")
    memory_b = harness.record_memory("notebook-2", "gradient descent basics")
    harness.give_feedback(memory_a.memory_id, "useful", rating=1.0)
    harness.give_feedback(memory_a.memory_id, "useful", rating=1.0)

    signals_a = harness.extractor.extract_for_memory(memory_a.memory_id, now=NOW)
    harness.updater.apply_signals(memory_a.memory_id, signals_a, now=NOW)

    metadata_a = harness.updater.metadata_for(memory_a.memory_id)
    metadata_b = harness.updater.metadata_for(memory_b.memory_id)

    assert metadata_a.supporting_evidence_count > 0
    assert metadata_b.supporting_evidence_count == 0
    assert metadata_b.successful_use_count == 0
    assert metadata_b.last_updated_at is None


def test_unchanged_original_memory_content():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "useful", rating=1.0)
    harness.give_feedback(memory.memory_id, "incorrect", rating=-1.0)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    harness.updater.apply_signals(memory.memory_id, signals, now=NOW)

    unchanged = harness.memory_service.get(memory.memory_id)
    assert unchanged.content == "gradient descent basics"
    assert unchanged.execution_id == memory.execution_id
    assert unchanged.outcome == memory.outcome
    assert unchanged.created_at == memory.created_at
    assert unchanged.memory_type == memory.memory_type


def test_quality_promotion_integration():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics")
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)
    harness.give_feedback(memory.memory_id, "successful", rating=1.0)

    signals = harness.extractor.extract_for_memory(memory.memory_id, now=NOW)
    harness.updater.apply_signals(memory.memory_id, signals, now=NOW)

    via_updater = harness.updater.quality_for(memory.memory_id, now=NOW)
    direct = harness.quality_assessor.assess(memory.memory_id, now=NOW)
    assert via_updater == direct

    decision_via_updater = harness.updater.promotion_decision_for(memory.memory_id, now=NOW)
    decision_direct = harness.promoter.evaluate(memory.memory_id, now=NOW)
    assert decision_via_updater == decision_direct
    assert decision_via_updater.eligible is True


def test_execution_level_update():
    harness = Harness()
    execution = harness.execute()

    result = harness.updater.update_from_execution(execution.execution_id, now=NOW)

    assert result.execution_id == execution.execution_id
    assert result.memory_id is None
    assert result.metadata is None
    assert len(result.signals) == 1
    assert result.signals[0].signal_type == "successful_strategy"
