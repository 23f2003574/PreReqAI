import json
from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_application import CONTEXT_KEY, LLMAgentMemoryApplicator
from backend.agent_memory_consolidation import LLMAgentMemoryConsolidator
from backend.agent_memory_feedback import LLMAgentMemoryFeedbackService
from backend.agent_memory_promotion import DEPRECATED, TRUSTED, LLMAgentMemoryPromoter
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


class ScriptedProvider(LLMProvider):
    """A real LLMProvider that replays one scripted response, for exercising
    the actual LLMAgentPlanningService.create() entry point."""

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
        self.consolidator = LLMAgentMemoryConsolidator(self.memory_service)
        self.quality_assessor = LLMAgentMemoryQualityAssessor(self.memory_service, self.feedback_service)
        self.promoter = LLMAgentMemoryPromoter(self.memory_service, self.quality_assessor)
        self.scorer = LLMAgentMemoryRelevanceScorer()
        self.applicator = LLMAgentMemoryApplicator(self.memory_service, self.scorer, self.promoter)
        self._counter = 0

    def execute(self):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        self.store.add(_plan(plan_id, "lookup"))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == SUCCEEDED
        return execution

    def record_memory(self, scope_id: str, content: str, memory_type: str = "strategy", backdate=None):
        execution = self.execute()
        memory = self.memory_service.record(
            execution.execution_id, {"scope_id": scope_id, "memory_type": memory_type, "content": content}
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

    def real_planning_service(self, script):
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


def _make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


def test_relevant_memory_application():
    harness = Harness()
    relevant = harness.record_memory(
        "notebook-1", "gradient descent optimizes the loss function", backdate=NOW
    )
    harness.record_memory("notebook-1", "completely unrelated database indexing tip", backdate=NOW)

    memory_context = harness.applicator.prepare("notebook-1", "gradient descent loss function", now=NOW)

    assert memory_context["scope_id"] == "notebook-1"
    assert memory_context["memories"][0]["memory_id"] == relevant.memory_id
    assert memory_context["memories"][0]["relevance_score"] > 0
    assert memory_context["memories"][0]["advisory"] is True


def test_trusted_vs_candidate_memories():
    harness = Harness()
    candidate = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    trusted = harness.record_memory("notebook-1", "gradient descent basics detailed", backdate=NOW)
    harness.trust(trusted.memory_id)

    memory_context = harness.applicator.prepare("notebook-1", "gradient descent basics", limit=2, now=NOW)
    ids_in_order = [entry["memory_id"] for entry in memory_context["memories"]]

    assert ids_in_order[0] == trusted.memory_id
    assert memory_context["memories"][0]["status"] == TRUSTED
    assert candidate.memory_id in ids_in_order


def test_deprecated_memory_exclusion():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    harness.promoter.deprecate(memory.memory_id, "turned out to be wrong", now=NOW)

    memory_context = harness.applicator.prepare("notebook-1", "gradient descent basics", now=NOW)
    assert memory_context["memories"] == []

    with_deprecated = harness.applicator.prepare(
        "notebook-1", "gradient descent basics", include_deprecated=True, now=NOW
    )
    assert [entry["memory_id"] for entry in with_deprecated["memories"]] == [memory.memory_id]
    assert with_deprecated["memories"][0]["status"] == DEPRECATED


def test_scope_isolation():
    harness = Harness()
    harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    other = harness.record_memory("notebook-2", "gradient descent basics", backdate=NOW)

    memory_context = harness.applicator.prepare("notebook-2", "gradient descent basics", now=NOW)

    assert [entry["memory_id"] for entry in memory_context["memories"]] == [other.memory_id]
    assert all(entry["scope_id"] == "notebook-2" for entry in memory_context["memories"])


def test_result_limits():
    harness = Harness()
    for i in range(5):
        harness.record_memory("notebook-1", f"gradient descent fact {i}", backdate=NOW)

    memory_context = harness.applicator.prepare("notebook-1", "gradient descent", limit=2, now=NOW)
    assert len(memory_context["memories"]) == 2

    with pytest.raises(ValueError):
        harness.applicator.prepare("notebook-1", "gradient descent", limit=0, now=NOW)


def test_provenance_preservation():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)

    memory_context = harness.applicator.prepare("notebook-1", "gradient descent basics", now=NOW)
    entry = memory_context["memories"][0]

    assert entry["memory_id"] == memory.memory_id
    assert entry["execution_id"] == memory.execution_id
    assert entry["scope_id"] == memory.scope_id
    assert entry["memory_type"] == memory.memory_type
    assert entry["outcome"] == memory.outcome
    assert isinstance(entry["relevance_score"], float)
    assert isinstance(entry["reason"], str) and entry["reason"]

    # applying memory never mutates the underlying record
    assert harness.memory_service.get(memory.memory_id).content == "gradient descent basics"


def test_duplicate_prevention_after_consolidation():
    harness = Harness()
    a = harness.record_memory("notebook-1", "gradient descent optimizes the loss function", backdate=NOW)
    b = harness.record_memory(
        "notebook-1", "gradient descent optimizes the loss function with tuning", backdate=NOW
    )
    consolidated = harness.consolidator.consolidate([a, b])

    memory_context = harness.applicator.prepare("notebook-1", "gradient descent loss function", now=NOW)
    ids_present = {entry["memory_id"] for entry in memory_context["memories"]}

    assert consolidated.memory_id in ids_present
    assert a.memory_id not in ids_present
    assert b.memory_id not in ids_present


def test_interaction_with_existing_agent_context():
    harness = Harness()
    memory = harness.record_memory("notebook-1", "gradient descent basics", backdate=NOW)
    existing_context = {"project_notes": "prefers concise derivations"}

    enriched = harness.applicator.apply("notebook-1", "gradient descent basics", context=existing_context, now=NOW)

    # existing project context is untouched and remains authoritative
    assert enriched["project_notes"] == "prefers concise derivations"
    assert existing_context == {"project_notes": "prefers concise derivations"}  # not mutated
    assert enriched[CONTEXT_KEY]["memories"][0]["memory_id"] == memory.memory_id

    # the enriched context is genuinely usable by the real planning entry point
    json.dumps(enriched)

    planning_service, provider = harness.real_planning_service(
        [_make_response(json.dumps({"steps": [{"action": "look it up", "tool": "lookup", "arguments": {}}]}))]
    )
    plan = planning_service.create("explain gradient descent", enriched)
    assert plan.steps[0].tool_name == "lookup"
    assert json.loads(provider.last_request.messages[-1]["content"])["context"] == enriched


def test_empty_memory_case():
    harness = Harness()

    memory_context = harness.applicator.prepare("empty-notebook", "anything", now=NOW)
    assert memory_context == {"scope_id": "empty-notebook", "task": "anything", "memories": []}

    enriched = harness.applicator.apply("empty-notebook", "anything", now=NOW)
    assert enriched[CONTEXT_KEY]["memories"] == []
