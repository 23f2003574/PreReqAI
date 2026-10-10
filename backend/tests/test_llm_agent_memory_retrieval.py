from datetime import datetime, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_retrieval import (
    InvalidMemoryQueryError,
    LLMAgentMemoryQuery,
    LLMAgentMemoryRetriever,
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
    """A plan store over several plans at once -- each test's plan_execution
    pipeline needs to run more than one execution to have several memories
    to retrieve among."""

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
    """A shared Commit #1/#12 pipeline that can execute several plans and
    record a Commit #1 memory for each -- the setup every test in this file
    needs to have real, provenance-linked memories to retrieve among."""

    def __init__(self):
        self.store = MultiPlanStore()

        registry = LLMToolRegistryService()
        registry.register("lookup", "Tool lookup", SCHEMA)
        registry.register("broken_lookup", "Tool broken_lookup", SCHEMA)

        invocation = LLMToolInvocationService(registry)
        permissions = LLMToolPermissionService(registry, invocation)
        for index, tool_name in enumerate(("lookup", "broken_lookup")):
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
        self.retriever = LLMAgentMemoryRetriever(self.memory_service)

    def record(self, plan_id: str, scope_id: str, memory_type: str, content: str, succeed: bool = True):
        tool_name = "lookup" if succeed else "broken_lookup"
        self.store.add(_plan(plan_id, tool_name))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == (SUCCEEDED if succeed else FAILED)
        return self.memory_service.record(
            execution.execution_id,
            {"scope_id": scope_id, "memory_type": memory_type, "content": content},
        )


def test_relevant_memories_ranked_first():
    harness = Harness()
    relevant = harness.record(
        "plan-1", "notebook-1", "strategy", "gradient descent optimizes the loss function"
    )
    harness.record("plan-2", "notebook-1", "strategy", "completely unrelated topic")

    results = harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent loss function")
    )

    assert results[0].memory_id == relevant.memory_id


def test_scope_isolation():
    harness = Harness()
    harness.record("plan-1", "notebook-1", "strategy", "gradient descent basics")
    other = harness.record("plan-2", "notebook-2", "strategy", "gradient descent basics")

    results = harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-2", query="gradient descent")
    )
    assert [item.memory_id for item in results] == [other.memory_id]

    # a scope-1 query must never surface scope-2 memories, matching or not
    results = harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent")
    )
    assert all(item.scope_id == "notebook-1" for item in results)


def test_memory_type_filter():
    harness = Harness()
    strategy = harness.record("plan-1", "notebook-1", "strategy", "call lookup with topic first")
    harness.record("plan-2", "notebook-1", "tool_usage", "call lookup with topic first")

    results = harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-1", query="lookup", memory_types=["strategy"])
    )
    assert [item.memory_id for item in results] == [strategy.memory_id]

    with pytest.raises(InvalidMemoryQueryError):
        harness.retriever.retrieve(
            LLMAgentMemoryQuery(scope_id="notebook-1", query="lookup", memory_types=["not-a-real-type"])
        )


def test_outcome_filter():
    harness = Harness()
    succeeded = harness.record("plan-1", "notebook-1", "strategy", "lookup worked", succeed=True)
    failed = harness.record("plan-2", "notebook-1", "failure_pattern", "lookup failed", succeed=False)

    only_succeeded = harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-1", query="lookup", outcome_filter=SUCCEEDED)
    )
    assert [item.memory_id for item in only_succeeded] == [succeeded.memory_id]

    only_failed = harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-1", query="lookup", outcome_filter=FAILED)
    )
    assert [item.memory_id for item in only_failed] == [failed.memory_id]

    with pytest.raises(InvalidMemoryQueryError):
        harness.retriever.retrieve(
            LLMAgentMemoryQuery(scope_id="notebook-1", query="lookup", outcome_filter="NOT_A_REAL_OUTCOME")
        )


def test_result_limit():
    harness = Harness()
    for i in range(5):
        harness.record("plan-%d" % i, "notebook-1", "strategy", f"fact number {i}")

    results = harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-1", query="fact", limit=2)
    )
    assert len(results) == 2

    with pytest.raises(ValueError):
        harness.retriever.retrieve(LLMAgentMemoryQuery(scope_id="notebook-1", query="fact", limit=0))

    with pytest.raises(ValueError):
        harness.retriever.retrieve(LLMAgentMemoryQuery(scope_id="notebook-1", query="fact", limit=-1))


def test_deterministic_ties():
    harness = Harness()
    for i in range(4):
        harness.record("plan-%d" % i, "notebook-1", "strategy", f"shared term number {i}")

    query = LLMAgentMemoryQuery(scope_id="notebook-1", query="shared term", limit=4)
    first_call = harness.retriever.retrieve(query)
    second_call = harness.retriever.retrieve(query)

    assert [item.memory_id for item in first_call] == [item.memory_id for item in second_call]


def test_empty_query_falls_back_to_recency():
    harness = Harness()
    older = harness.record("plan-1", "notebook-1", "strategy", "first fact")
    newer = harness.record("plan-2", "notebook-1", "strategy", "second fact")

    results = harness.retriever.retrieve(LLMAgentMemoryQuery(scope_id="notebook-1", query=""))

    assert len(results) == 2
    assert results[0].memory_id == newer.memory_id
    assert results[1].memory_id == older.memory_id


def test_no_match_and_empty_scope():
    harness = Harness()
    harness.record("plan-1", "notebook-1", "strategy", "gradient descent basics")

    assert harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="empty-scope", query="anything")
    ) == []

    # a query with no overlapping terms still returns every scope match,
    # just all scored 0.0 and ordered by recency
    results = harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-1", query="completely unrelated words")
    )
    assert len(results) == 1


def test_provenance_preserved():
    harness = Harness()
    harness.store.add(_plan("plan-1", "lookup"))
    execution = harness.plan_execution.execute("plan-1", "user:ada")
    recorded = harness.memory_service.record(
        execution.execution_id,
        {"scope_id": "notebook-1", "memory_type": "strategy", "content": "gradient descent basics"},
    )

    results = harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent")
    )

    assert results[0].execution_id == execution.execution_id
    assert results[0].execution_id == recorded.execution_id


def test_read_only():
    harness = Harness()
    harness.record("plan-1", "notebook-1", "strategy", "gradient descent basics")

    before = harness.memory_service.list("notebook-1")
    harness.retriever.retrieve(LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent"))
    harness.retriever.rank(before, "gradient descent")
    after = harness.memory_service.list("notebook-1")

    assert [item.memory_id for item in before] == [item.memory_id for item in after]
