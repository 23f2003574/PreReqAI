from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_relevance_scoring import LLMAgentMemoryRelevanceScorer, ScoredMemory
from backend.agent_memory_retrieval import LLMAgentMemoryQuery, LLMAgentMemoryRetriever
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
        self.retriever = LLMAgentMemoryRetriever(self.memory_service)
        self.scorer = LLMAgentMemoryRelevanceScorer()

    def record(self, plan_id: str, scope_id: str, memory_type: str, content: str, succeed: bool = True):
        tool_name = "lookup" if succeed else "broken_lookup"
        self.store.add(_plan(plan_id, tool_name))
        execution = self.plan_execution.execute(plan_id, "user:ada")
        assert execution.status == (SUCCEEDED if succeed else FAILED)
        recorded = self.memory_service.record(
            execution.execution_id,
            {"scope_id": scope_id, "memory_type": memory_type, "content": content},
        )
        # backdate created_at so recency tests can control age deterministically,
        # without reaching into Commit #1's own store internals to do it.
        recorded.created_at = NOW
        self.memory_service.store.save(recorded)
        return recorded


def test_highly_relevant_memory_scores_higher():
    harness = Harness()
    relevant = harness.record(
        "plan-1", "notebook-1", "strategy", "gradient descent optimizes the loss function"
    )
    irrelevant = harness.record("plan-2", "notebook-1", "strategy", "completely unrelated topic")
    query = LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent loss function")

    relevant_score = harness.scorer.score(relevant, query, now=NOW)
    irrelevant_score = harness.scorer.score(irrelevant, query, now=NOW)

    assert relevant_score > irrelevant_score


def test_irrelevant_memory_scores_lower():
    harness = Harness()
    memory = harness.record("plan-1", "notebook-1", "strategy", "gradient descent basics")
    query = LLMAgentMemoryQuery(scope_id="notebook-1", query="something entirely else")

    score = harness.scorer.score(memory, query, now=NOW)

    # relevance component is 0, so only the (bounded) type/outcome/recency
    # share remains -- well under the 0.55 relevance weight alone.
    assert score < 0.55


def test_bounded_score_range():
    harness = Harness()
    memory = harness.record("plan-1", "notebook-1", "strategy", "gradient descent basics")
    query = LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent basics")

    score = harness.scorer.score(memory, query, now=NOW)
    assert 0.0 <= score <= 1.0


def test_recency_behavior_bounded_by_relevance():
    harness = Harness()
    recent = harness.record("plan-1", "notebook-1", "strategy", "gradient descent basics")
    old = harness.record("plan-2", "notebook-1", "strategy", "gradient descent basics")
    old.created_at = NOW - timedelta(days=365)
    harness.memory_service.store.save(old)

    query = LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent basics")

    recent_score = harness.scorer.score(recent, query, now=NOW)
    old_score = harness.scorer.score(old, query, now=NOW)

    # recency separates two identically-relevant memories...
    assert recent_score > old_score
    # ...but never by more than recency's own 0.15 share of the total.
    assert recent_score - old_score <= 0.15 + 1e-9

    # a highly relevant OLD memory still beats a barely relevant RECENT one --
    # recency alone can never override a strong relevance gap.
    barely_relevant_recent = harness.record("plan-3", "notebook-1", "strategy", "nothing to do with it")
    query2 = LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent basics")
    assert harness.scorer.score(old, query2, now=NOW) > harness.scorer.score(
        barely_relevant_recent, query2, now=NOW
    )


def test_outcome_signal():
    harness = Harness()
    succeeded = harness.record("plan-1", "notebook-1", "strategy", "lookup worked", succeed=True)
    failed = harness.record("plan-2", "notebook-1", "strategy", "lookup worked", succeed=False)
    query = LLMAgentMemoryQuery(scope_id="notebook-1", query="lookup worked")

    assert harness.scorer.score(succeeded, query, now=NOW) > harness.scorer.score(failed, query, now=NOW)

    # an explicit outcome_filter hard-prefers only the matching outcome
    filtered_query = LLMAgentMemoryQuery(scope_id="notebook-1", query="lookup worked", outcome_filter=FAILED)
    assert harness.scorer.score(failed, filtered_query, now=NOW) > harness.scorer.score(
        succeeded, filtered_query, now=NOW
    )


def test_type_signal():
    harness = Harness()
    memory = harness.record("plan-1", "notebook-1", "strategy", "lookup worked")

    preferred_query = LLMAgentMemoryQuery(
        scope_id="notebook-1", query="lookup worked", memory_types=["strategy"]
    )
    other_query = LLMAgentMemoryQuery(
        scope_id="notebook-1", query="lookup worked", memory_types=["tool_usage"]
    )

    assert harness.scorer.score(memory, preferred_query, now=NOW) > harness.scorer.score(
        memory, other_query, now=NOW
    )


def test_scope_mismatch_scores_zero():
    harness = Harness()
    memory = harness.record("plan-1", "notebook-1", "strategy", "gradient descent basics")
    query = LLMAgentMemoryQuery(scope_id="notebook-2", query="gradient descent basics")

    assert harness.scorer.score(memory, query, now=NOW) == 0.0


def test_deterministic_scores():
    harness = Harness()
    memory = harness.record("plan-1", "notebook-1", "strategy", "gradient descent basics")
    query = LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent basics")

    first = harness.scorer.score(memory, query, now=NOW)
    second = harness.scorer.score(memory, query, now=NOW)

    assert first == second


def test_stable_tie_breaking():
    harness = Harness()
    memories = [
        harness.record("plan-%d" % i, "notebook-1", "strategy", "shared term")
        for i in range(4)
    ]
    for memory in memories:
        memory.created_at = NOW
        harness.memory_service.store.save(memory)

    query = LLMAgentMemoryQuery(scope_id="notebook-1", query="shared term")

    first_call = harness.scorer.rank(memories, query, now=NOW)
    second_call = harness.scorer.rank(memories, query, now=NOW)

    assert [item.memory.memory_id for item in first_call] == [item.memory.memory_id for item in second_call]
    # equal scores broken by memory_id, ascending
    assert [item.memory.memory_id for item in first_call] == sorted(item.memory.memory_id for item in first_call)


def test_ranking_preserves_provenance_and_original_memory():
    harness = Harness()
    recorded = harness.record("plan-1", "notebook-1", "strategy", "gradient descent basics")
    query = LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent basics")

    ranked = harness.scorer.rank([recorded], query, now=NOW)

    assert len(ranked) == 1
    assert isinstance(ranked[0], ScoredMemory)
    assert ranked[0].memory is recorded
    assert ranked[0].memory.execution_id == recorded.execution_id
    assert ranked[0].memory.content == "gradient descent basics"
    assert isinstance(ranked[0].relevance_score, float)
    assert isinstance(ranked[0].reason, str) and ranked[0].reason


def test_integration_with_commit_2_retrieval_path():
    harness = Harness()
    relevant = harness.record(
        "plan-1", "notebook-1", "strategy", "gradient descent optimizes the loss function"
    )
    harness.record("plan-2", "notebook-1", "strategy", "completely unrelated topic")

    scored_retriever = LLMAgentMemoryRetriever(harness.memory_service, scorer=harness.scorer)
    results = scored_retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent loss function"), now=NOW
    )

    assert results[0].memory_id == relevant.memory_id
    # the plain Commit #2 retriever (no scorer) still behaves exactly as before
    plain_results = harness.retriever.retrieve(
        LLMAgentMemoryQuery(scope_id="notebook-1", query="gradient descent loss function")
    )
    assert plain_results[0].memory_id == relevant.memory_id
