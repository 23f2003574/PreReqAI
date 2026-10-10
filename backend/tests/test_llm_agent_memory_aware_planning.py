import json
from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_application import LLMAgentMemoryApplicator
from backend.agent_memory_aware_planning import (
    PLANNING_CONTEXT_KEY,
    LLMAgentMemoryAwarePlan,
    LLMAgentMemoryAwarePlanningService,
)
from backend.agent_memory_feedback import LLMAgentMemoryFeedbackService
from backend.agent_memory_promotion import LLMAgentMemoryPromoter
from backend.agent_memory_quality_assessment import LLMAgentMemoryQualityAssessor
from backend.agent_memory_relevance_scoring import LLMAgentMemoryRelevanceScorer
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import LLMAgentPlanningService, READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
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


class ScriptedProvider(LLMProvider):
    def __init__(self, script):
        self._script = list(script)
        self.calls = 0
        self.last_request = None

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        self.calls += 1
        self.last_request = request
        return self._script[min(self.calls - 1, len(self._script) - 1)]

    def stream(self, request):
        raise NotImplementedError


def _make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


PLAN_SCRIPT = [
    _make_response(json.dumps({"steps": [{"action": "look it up", "tool": "lookup", "arguments": {}}]}))
]


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
        orchestrator = LLMToolCallingOrchestrationService(
            invocation_service=invocation, permission_service=permissions, execution_service=execution,
            result_service=results, idempotency_service=idempotency, control_service=control,
            retry_service=retry,
        )

        validation_service = LLMAgentPlanValidationService(
            self.store, self.registry, permissions, invocation_service=invocation
        )
        step_execution = LLMAgentExecutionService(self.store, validation_service, orchestrator)
        self.plan_execution = LLMAgentPlanExecutionService(self.store, validation_service, step_execution)
        self.memory_service = LLMAgentMemoryService(self.plan_execution)
        self.feedback_service = LLMAgentMemoryFeedbackService(self.memory_service, self.plan_execution)
        self.quality_assessor = LLMAgentMemoryQualityAssessor(self.memory_service, self.feedback_service)
        self.promoter = LLMAgentMemoryPromoter(self.memory_service, self.quality_assessor)
        self.scorer = LLMAgentMemoryRelevanceScorer()
        self.applicator = LLMAgentMemoryApplicator(self.memory_service, self.scorer, self.promoter)
        self._counter = 0

    def execute(self, succeed: bool = True):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        tool_name = "lookup" if succeed else "broken_lookup"
        self.store.add(_plan(plan_id, tool_name))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == (SUCCEEDED if succeed else FAILED)
        return execution

    def record_memory(self, scope_id: str, content: str, succeed: bool = True, backdate=None):
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

    def trust(self, memory_id):
        self.give_feedback(memory_id, "successful", rating=1.0)
        self.give_feedback(memory_id, "successful", rating=1.0)
        return self.promoter.promote(memory_id, now=NOW)

    def planning_service(self, script):
        config_service = LLMProviderConfigService()
        config_service.register(
            LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True)
        )
        routing_service = LLMModelRoutingService(config_service)
        routing_service.register_capability_profile(
            "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
        )
        context_service = LLMContextService()
        provider = ScriptedProvider(script)
        orchestration_service = LLMRequestOrchestrationService(
            context_service=context_service, routing_service=routing_service, providers={"openai": provider},
        )
        return LLMAgentPlanningService(self.registry, orchestration_service, context_service), provider

    def aware_planning_service(self, script):
        planning_service, provider = self.planning_service(script)
        return LLMAgentMemoryAwarePlanningService(planning_service, self.applicator), provider


def test_planning_with_relevant_trusted_memory():
    harness = Harness()
    trusted = harness.record_memory("notebook-1", "gradient descent optimizes the loss function", backdate=NOW)
    harness.trust(trusted.memory_id)

    aware_service, provider = harness.aware_planning_service(PLAN_SCRIPT)
    result = aware_service.create("notebook-1", "gradient descent loss function", now=NOW)

    assert isinstance(result, LLMAgentMemoryAwarePlan)
    assert result.plan.status == READY
    ids = [entry["memory_id"] for entry in result.memory_context.applicable_memories]
    assert trusted.memory_id in ids
    assert any(entry["memory_id"] == trusted.memory_id for entry in result.memory_context.memory_evidence["proven_strategies"])

    sent_context = json.loads(provider.last_request.messages[-1]["content"])["context"]
    assert sent_context[PLANNING_CONTEXT_KEY]["memory_evidence"]["proven_strategies"][0]["memory_id"] == trusted.memory_id


def test_planning_with_no_memory():
    harness = Harness()
    aware_service, provider = harness.aware_planning_service(PLAN_SCRIPT)

    result = aware_service.create("empty-notebook", "explain gradient descent", now=NOW)

    assert result.memory_context.applicable_memories == []
    assert result.memory_context.memory_evidence == {"proven_strategies": [], "known_failure_patterns": []}
    assert result.memory_context.memory_provenance == []
    assert result.plan.status == READY


def test_low_quality_deprecated_memory_exclusion():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    harness.promoter.deprecate(memory.memory_id, "found to be wrong", now=NOW)

    aware_service, _provider = harness.aware_planning_service(PLAN_SCRIPT)
    result = aware_service.create("notebook-1", "gradient descent basics", now=NOW)

    assert result.memory_context.applicable_memories == []
    assert memory.memory_id not in [e["memory_id"] for e in result.memory_context.memory_provenance]


def test_conflicting_memories():
    harness = Harness()
    succeeded = harness.record_memory("notebook-1", "gradient descent basics", succeed=True, backdate=NOW)
    failed = harness.record_memory("notebook-1", "gradient descent basics alt", succeed=False, backdate=NOW)

    aware_service, _provider = harness.aware_planning_service(PLAN_SCRIPT)
    result = aware_service.create("notebook-1", "gradient descent basics", now=NOW)

    proven_ids = {e["memory_id"] for e in result.memory_context.memory_evidence["proven_strategies"]}
    failure_ids = {e["memory_id"] for e in result.memory_context.memory_evidence["known_failure_patterns"]}
    assert succeeded.memory_id in proven_ids
    assert failed.memory_id in failure_ids
    # both sides of the disagreement remain visible, neither suppressed
    assert proven_ids and failure_ids


def test_scope_isolation():
    harness = Harness()
    harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    other = harness.record_memory("notebook-2", "gradient descent basics", backdate=NOW)

    aware_service, _provider = harness.aware_planning_service(PLAN_SCRIPT)
    result = aware_service.create("notebook-2", "gradient descent basics", now=NOW)

    ids = [e["memory_id"] for e in result.memory_context.applicable_memories]
    assert ids == [other.memory_id]
    assert all(e["memory_id"] == other.memory_id for e in result.memory_context.memory_provenance)


def test_provenance_propagation():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)

    aware_service, _provider = harness.aware_planning_service(PLAN_SCRIPT)
    result = aware_service.create("notebook-1", "gradient descent basics", now=NOW)

    applied_entry = result.memory_context.applicable_memories[0]
    provenance_entry = result.memory_context.memory_provenance[0]

    assert provenance_entry["memory_id"] == applied_entry["memory_id"] == memory.memory_id
    assert provenance_entry["execution_id"] == memory.execution_id
    assert provenance_entry["status"] == applied_entry["status"]
    assert provenance_entry["relevance_score"] == applied_entry["relevance_score"]

    # planning never mutates the underlying memory
    assert harness.memory_service.get(memory.memory_id).content == "gradient descent basics"


def test_existing_planning_behavior_remains_valid():
    harness = Harness()
    # no memory recorded at all -- memory-aware planning should behave
    # exactly like calling the real planner directly with the same script

    direct_service, direct_provider = harness.planning_service(PLAN_SCRIPT)
    direct_plan = direct_service.create("explain gradient descent")

    aware_service, aware_provider = harness.aware_planning_service(PLAN_SCRIPT)
    result = aware_service.create("empty-notebook", "explain gradient descent", now=NOW)

    assert result.plan.status == direct_plan.status
    assert [s.tool_name for s in result.plan.steps] == [s.tool_name for s in direct_plan.steps]
    assert [s.action for s in result.plan.steps] == [s.action for s in direct_plan.steps]
