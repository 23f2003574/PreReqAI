import pytest

from backend.agent_execution_memory import InMemoryLLMAgentMemoryStore, LLMAgentMemory, LLMAgentMemoryService
from backend.agent_policy_engine import DENY, LLMAgentPolicyService
from backend.agent_task_context import LLMAgentTaskContextService, UnknownTaskContextError
from backend.agent_task_context_resolution import (
    InvalidTaskContextResolutionError,
    LLMAgentTaskContextResolver,
    ResolvedAgentTaskContext,
    TaskContextScopeMismatchError,
)
from backend.llm.context_freshness import LLMContextFreshnessService
from backend.llm.context_provenance import LLMContextProvenanceService
from backend.llm.context_snapshot import LLMContextSnapshotService
from backend.llm.project_context import LLMProjectContextService


def _seed_memory(store, scope_id, content, memory_type="strategy", outcome="succeeded"):
    memory = LLMAgentMemory(
        scope_id=scope_id, execution_id="exec-1", memory_type=memory_type, content=content, outcome=outcome
    )
    return store.save(memory)


def _memory_service(store=None):
    return LLMAgentMemoryService(plan_execution_service=None, store=store or InMemoryLLMAgentMemoryStore())


# --- explicit task context is preserved ---------------------------------------------


def test_explicit_task_context_is_preserved():
    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="summarize the notebook",
        relevant_context=[{"context_id": "explicit-1", "content": "explicit fact", "context_type": "fact"}],
    )
    resolver = LLMAgentTaskContextResolver(task_context_service)

    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    assert isinstance(result, ResolvedAgentTaskContext)
    assert any(entry["context_id"] == "explicit-1" for entry in result.selected_context)
    assert "__task_context__" in result.resolution_reasons
    assert result.task_context == task_context


def test_explicit_context_provenance_is_preserved_in_result():
    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="use context",
        relevant_context=[{"context_id": "explicit-1", "content": "explicit fact", "context_type": "fact"}],
    )
    assert len(task_context.provenance) == 1  # Commit #1 auto-derives this

    resolver = LLMAgentTaskContextResolver(task_context_service)
    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    assert any(entry.context_id == "explicit-1" for entry in result.provenance)


# --- relevant existing context is included -------------------------------------------


def test_relevant_project_context_is_included():
    project_context_service = LLMProjectContextService()
    on_topic = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    off_topic = project_context_service.create("scope-1", "fact", "unrelated grocery shopping list")

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="analyze the notebook dependency graph"
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    selected_ids = {entry["context_id"] for entry in result.selected_context}
    assert on_topic.context_id in selected_ids
    assert any(entry.context_id == on_topic.context_id for entry in result.provenance)


def test_no_project_context_service_pulls_nothing_extra():
    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextResolver(task_context_service)

    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    assert result.selected_context == []
    assert result.excluded_context == []


# --- relevant agent memory is included when available ----------------------------------


def test_relevant_memory_is_included_when_service_supplied():
    memory_store = InMemoryLLMAgentMemoryStore()
    on_topic = _seed_memory(memory_store, "scope-1", "notebook dependency graph strategy that worked")
    _seed_memory(memory_store, "scope-1", "unrelated grocery list heuristic")
    memory_service = _memory_service(memory_store)

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="analyze the notebook dependency graph"
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, memory_service=memory_service)
    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    memory_ids = {memory.memory_id for memory in result.selected_memories}
    assert on_topic.memory_id in memory_ids
    assert on_topic.memory_id in result.resolution_reasons
    assert any(entry.context_id == on_topic.memory_id and entry.source_type == "agent_memory" for entry in result.provenance)


def test_no_memory_service_yields_no_memories():
    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextResolver(task_context_service)

    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    assert result.selected_memories == []


# --- irrelevant/stale context is excluded -----------------------------------------------


def test_irrelevant_context_is_excluded():
    project_context_service = LLMProjectContextService()
    project_context_service.create("scope-1", "fact", "completely unrelated grocery shopping list")

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    assert result.selected_context == []
    assert len(result.excluded_context) == 1
    reason = next(iter(result.resolution_reasons.values()))
    assert "irrelevant" in reason


def test_relevant_but_over_budget_context_is_excluded():
    project_context_service = LLMProjectContextService()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis " + "x" * 4000)

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(
        task_context_service, project_context_service=project_context_service, token_budget=1
    )
    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    assert result.selected_context == []
    assert len(result.excluded_context) == 1
    reason = next(iter(result.resolution_reasons.values()))
    assert "budget" in reason


def test_stale_context_is_excluded():
    project_context_service = LLMProjectContextService()
    provenance_service = LLMContextProvenanceService(project_context_service)
    snapshot_service = LLMContextSnapshotService()
    freshness_service = LLMContextFreshnessService(project_context_service, provenance_service, snapshot_service)

    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    provenance_service.attach(
        context.context_id,
        {"source_type": "project_context", "source_id": context.context_id, "excerpt": "original"},
    )
    # updating the context after provenance was recorded makes it STALE
    project_context_service.update(context.context_id, "notebook dependency graph analysis, revised")

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(
        task_context_service,
        project_context_service=project_context_service,
        freshness_service=freshness_service,
    )
    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    assert result.selected_context == []
    excluded_ids = {entry["context_id"] for entry in result.excluded_context}
    assert context.context_id in excluded_ids
    assert "stale" in result.resolution_reasons[context.context_id]


def test_unauthorized_context_is_excluded():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1",
        "deny-context",
        [{"rule_id": "deny-it", "effect": DENY, "match": {"context_id": context.context_id}}],
    )

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(
        task_context_service, project_context_service=project_context_service, policy_service=policy_service
    )
    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    excluded_ids = {entry["context_id"] for entry in result.excluded_context}
    assert context.context_id in excluded_ids
    assert "denied" in result.resolution_reasons[context.context_id]


def test_already_explicit_context_is_not_duplicated():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="notebook dependency graph analysis",
        relevant_context=[context],
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    selected_ids = [entry["context_id"] for entry in result.selected_context]
    assert selected_ids.count(context.context_id) == 1
    excluded_ids = {entry["context_id"] for entry in result.excluded_context}
    assert context.context_id in excluded_ids
    assert "already present" in result.resolution_reasons[context.context_id]


# --- scope isolation ---------------------------------------------------------------------


def test_scope_isolation_across_project_context():
    project_context_service = LLMProjectContextService()
    project_context_service.create("scope-2", "fact", "notebook dependency graph analysis")

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    assert result.selected_context == []
    assert result.excluded_context == []


def test_scope_mismatch_is_rejected():
    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextResolver(task_context_service)

    with pytest.raises(TaskContextScopeMismatchError):
        resolver.resolve(task_context.task_id, "agent-1", "scope-2")
    with pytest.raises(TaskContextScopeMismatchError):
        resolver.resolve(task_context.task_id, "agent-2", "scope-1")


def test_unknown_task_id_propagates():
    task_context_service = LLMAgentTaskContextService()
    resolver = LLMAgentTaskContextResolver(task_context_service)

    with pytest.raises(UnknownTaskContextError):
        resolver.resolve("missing-task", "agent-1", "scope-1")


def test_invalid_identifiers_rejected():
    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    resolver = LLMAgentTaskContextResolver(task_context_service)

    with pytest.raises(InvalidTaskContextResolutionError):
        resolver.resolve(task_context.task_id, "", "scope-1")
    with pytest.raises(InvalidTaskContextResolutionError):
        resolver.resolve(task_context.task_id, "agent-1", "")


# --- provenance survives resolution -------------------------------------------------------


def test_provenance_covers_every_injected_source():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    memory_store = InMemoryLLMAgentMemoryStore()
    memory = _seed_memory(memory_store, "scope-1", "notebook dependency graph strategy")
    memory_service = _memory_service(memory_store)

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(
        task_context_service, project_context_service=project_context_service, memory_service=memory_service
    )
    result = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    provenance_ids = {entry.context_id for entry in result.provenance}
    assert context.context_id in provenance_ids
    assert memory.memory_id in provenance_ids


def test_provenance_is_deterministic_and_not_duplicated_across_calls():
    project_context_service = LLMProjectContextService()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    first = resolver.resolve(task_context.task_id, "agent-1", "scope-1")
    second = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    first_ids = sorted(entry.provenance_id for entry in first.provenance)
    second_ids = sorted(entry.provenance_id for entry in second.provenance)
    assert len(first.provenance) == len(second.provenance)
    assert [entry.context_id for entry in first.provenance] == [entry.context_id for entry in second.provenance]


# --- resolution is side-effect free ---------------------------------------------------------


def test_resolution_is_side_effect_free():
    project_context_service = LLMProjectContextService()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    memory_store = InMemoryLLMAgentMemoryStore()
    memory = _seed_memory(memory_store, "scope-1", "notebook dependency graph strategy")
    memory_service = _memory_service(memory_store)

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(
        task_context_service, project_context_service=project_context_service, memory_service=memory_service
    )
    resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    assert task_context_service.get(task_context.task_id) == task_context
    assert project_context_service.get(context.context_id) == context
    assert memory_service.get(memory.memory_id) == memory
    assert project_context_service.list("scope-1") == [context]
    assert memory_service.list("scope-1") == [memory]


def test_resolution_is_deterministic_for_identical_inputs():
    project_context_service = LLMProjectContextService()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    project_context_service.create("scope-1", "fact", "an unrelated shopping list")

    task_context_service = LLMAgentTaskContextService()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    first = resolver.resolve(task_context.task_id, "agent-1", "scope-1")
    second = resolver.resolve(task_context.task_id, "agent-1", "scope-1")

    assert [e["context_id"] for e in first.selected_context] == [e["context_id"] for e in second.selected_context]
    assert [e["context_id"] for e in first.excluded_context] == [e["context_id"] for e in second.excluded_context]
    assert first.resolution_reasons == second.resolution_reasons
