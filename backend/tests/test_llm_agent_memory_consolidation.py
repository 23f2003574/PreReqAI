from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_consolidation import (
    EmptyConsolidationGroupError,
    LLMAgentMemoryConsolidationResult,
    LLMAgentMemoryConsolidator,
    MixedScopeConsolidationError,
)
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
        self.consolidator = LLMAgentMemoryConsolidator(self.memory_service)
        self._counter = 0

    def record(self, scope_id: str, memory_type: str, content: str, succeed: bool = True):
        self._counter += 1
        plan_id = f"plan-{self._counter}"
        tool_name = "lookup" if succeed else "broken_lookup"
        self.store.add(_plan(plan_id, tool_name))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == (SUCCEEDED if succeed else FAILED)
        return self.memory_service.record(
            execution.execution_id,
            {"scope_id": scope_id, "memory_type": memory_type, "content": content},
        )


GRADIENT_A = "gradient descent optimizes the loss function using learning rate"
GRADIENT_B = "gradient descent optimizes the loss function with learning rate tuning"
UNRELATED = "completely different topic about databases and indexes"


def test_duplicate_detection():
    harness = Harness()
    a = harness.record("notebook-1", "strategy", GRADIENT_A)
    b = harness.record("notebook-1", "strategy", GRADIENT_B)
    c = harness.record("notebook-1", "strategy", UNRELATED)

    groups = harness.consolidator.find_duplicates([a, b, c])

    assert len(groups) == 1
    assert {m.memory_id for m in groups[0]} == {a.memory_id, b.memory_id}


def test_related_memory_consolidation():
    harness = Harness()
    a = harness.record("notebook-1", "strategy", GRADIENT_A)
    b = harness.record("notebook-1", "strategy", GRADIENT_B)

    consolidated = harness.consolidator.consolidate([a, b])

    assert consolidated.scope_id == "notebook-1"
    assert consolidated.memory_type == "strategy"
    assert consolidated.content["consolidated"] is True
    assert consolidated.content["summary"] in (a.content, b.content)
    assert {s["memory_id"] for s in consolidated.content["sources"]} == {a.memory_id, b.memory_id}
    # the new record is itself retrievable, exactly like any Commit #1 memory
    assert harness.memory_service.get(consolidated.memory_id).memory_id == consolidated.memory_id


def test_scope_isolation():
    harness = Harness()
    a1 = harness.record("notebook-1", "strategy", GRADIENT_A)
    b1 = harness.record("notebook-1", "strategy", GRADIENT_B)
    a2 = harness.record("notebook-2", "strategy", GRADIENT_A)
    b2 = harness.record("notebook-2", "strategy", GRADIENT_B)

    groups = harness.consolidator.find_duplicates([a1, b1, a2, b2])

    assert len(groups) == 2
    for group in groups:
        assert len({m.scope_id for m in group}) == 1

    with pytest.raises(MixedScopeConsolidationError):
        harness.consolidator.consolidate([a1, a2])

    result = harness.consolidator.consolidate_scope("notebook-1")
    assert result.scope_id == "notebook-1"
    assert len(result.consolidated) == 1
    assert result.consolidated[0].scope_id == "notebook-1"

    # notebook-2's own memories were never touched by notebook-1's consolidation
    assert harness.memory_service.get(a2.memory_id).content == GRADIENT_A
    assert harness.memory_service.get(b2.memory_id).content == GRADIENT_B


def test_provenance_preservation():
    harness = Harness()
    a = harness.record("notebook-1", "strategy", GRADIENT_A)
    b = harness.record("notebook-1", "strategy", GRADIENT_B)

    consolidated = harness.consolidator.consolidate([a, b])

    sources_by_id = {s["memory_id"]: s for s in consolidated.content["sources"]}
    assert sources_by_id[a.memory_id]["execution_id"] == a.execution_id
    assert sources_by_id[b.memory_id]["execution_id"] == b.execution_id
    assert sources_by_id[a.memory_id]["outcome"] == a.outcome
    assert sources_by_id[b.memory_id]["outcome"] == b.outcome
    # the consolidated record's own execution_id is a real, verifiable link
    assert consolidated.execution_id in (a.execution_id, b.execution_id)

    # originals remain independently recoverable, unmodified, after consolidation
    assert harness.memory_service.get(a.memory_id).content == GRADIENT_A
    assert harness.memory_service.get(b.memory_id).content == GRADIENT_B


def test_contradictory_outcomes_preserved():
    harness = Harness()
    succeeded = harness.record("notebook-1", "strategy", GRADIENT_A, succeed=True)
    failed = harness.record("notebook-1", "strategy", GRADIENT_B, succeed=False)

    groups = harness.consolidator.find_duplicates([succeeded, failed])
    assert len(groups) == 1

    consolidated = harness.consolidator.consolidate(groups[0])

    # both outcomes are recorded, neither silently dropped or overwritten
    assert consolidated.content["outcomes"] == [FAILED, SUCCEEDED]
    # the winning top-level outcome prefers the proven (SUCCEEDED) member
    assert consolidated.outcome == SUCCEEDED
    assert consolidated.execution_id == succeeded.execution_id

    # the failed original is still there, exactly as recorded
    assert harness.memory_service.get(failed.memory_id).outcome == FAILED


def test_empty_and_single_memory_groups():
    harness = Harness()
    solo = harness.record("notebook-1", "strategy", GRADIENT_A)

    assert harness.consolidator.find_duplicates([]) == []
    assert harness.consolidator.find_duplicates([solo]) == []

    with pytest.raises(EmptyConsolidationGroupError):
        harness.consolidator.consolidate([])

    result = harness.consolidator.consolidate([solo])
    assert result is solo

    # no new record was created for a singleton group
    scope_memories = harness.memory_service.list("notebook-1")
    assert [m.memory_id for m in scope_memories] == [solo.memory_id]


def test_deterministic_results():
    harness = Harness()
    a = harness.record("notebook-1", "strategy", GRADIENT_A)
    b = harness.record("notebook-1", "strategy", GRADIENT_B)
    c = harness.record("notebook-1", "strategy", UNRELATED)

    groups_first = harness.consolidator.find_duplicates([c, b, a])
    groups_second = harness.consolidator.find_duplicates([a, c, b])

    assert [[m.memory_id for m in group] for group in groups_first] == [
        [m.memory_id for m in group] for group in groups_second
    ]

    first = harness.consolidator.consolidate([a, b])
    second = harness.consolidator.consolidate([a, b])

    assert first.content["summary"] == second.content["summary"]
    assert first.content["sources"] == second.content["sources"]
    assert first.content["outcomes"] == second.content["outcomes"]
    assert first.execution_id == second.execution_id


def test_consolidation_kept_separate_from_retrieval():
    """Consolidation never calls into, or is called from, Commit #2/#3 --
    it only ever produces ordinary LLMAgentMemory records that those
    services can retrieve/score exactly like any other."""
    from backend.agent_memory_retrieval import LLMAgentMemoryQuery, LLMAgentMemoryRetriever

    harness = Harness()
    a = harness.record("notebook-1", "strategy", GRADIENT_A)
    b = harness.record("notebook-1", "strategy", GRADIENT_B)
    consolidated = harness.consolidator.consolidate([a, b])

    retriever = LLMAgentMemoryRetriever(harness.memory_service)
    results = retriever.retrieve(LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent"))

    assert consolidated.memory_id in {m.memory_id for m in results}
    assert isinstance(harness.consolidator.consolidate_scope("notebook-1"), LLMAgentMemoryConsolidationResult)
