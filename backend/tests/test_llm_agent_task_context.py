import dataclasses

import pytest

from backend.agent_task_context import (
    InvalidTaskContextError,
    JsonTaskContextStore,
    LLMAgentTaskContext,
    LLMAgentTaskContextService,
    LLMAgentTaskContextSnapshot,
    UnknownTaskContextError,
)
from backend.llm.project_context import LLMProjectContext


def _service():
    return LLMAgentTaskContextService()


def _project_context(scope_id="scope-1", content="the quick brown fox", context_type="fact"):
    return LLMProjectContext(scope_id=scope_id, context_type=context_type, content=content)


# --- create/get/update lifecycle -------------------------------------------------


def test_create_get_lifecycle():
    service = _service()

    task_context = service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="summarize the notebook",
        constraints=["read-only"],
        inputs={"notebook_id": "nb-1"},
    )

    assert isinstance(task_context, LLMAgentTaskContext)
    assert task_context.agent_id == "agent-1"
    assert task_context.scope_id == "scope-1"
    assert task_context.objective == "summarize the notebook"
    assert task_context.constraints == ["read-only"]
    assert task_context.inputs == {"notebook_id": "nb-1"}
    assert task_context.relevant_context == []
    assert task_context.provenance == []

    fetched = service.get(task_context.task_id)
    assert fetched == task_context


def test_update_changes_named_fields():
    service = _service()
    task_context = service.create(agent_id="agent-1", scope_id="scope-1", objective="draft a plan")

    updated = service.update(task_context.task_id, {"objective": "revise the plan", "inputs": {"k": "v"}})

    assert updated.objective == "revise the plan"
    assert updated.inputs == {"k": "v"}


def test_update_unknown_task_raises():
    service = _service()
    with pytest.raises(UnknownTaskContextError):
        service.update("missing-task", {"objective": "x"})


def test_get_unknown_task_raises():
    service = _service()
    with pytest.raises(UnknownTaskContextError):
        service.get("missing-task")


def test_json_store_round_trips_across_service_instances(tmp_path):
    path = tmp_path / "task_contexts.json"
    service_a = LLMAgentTaskContextService(store=JsonTaskContextStore(path))
    task_context = service_a.create(
        agent_id="agent-1", scope_id="scope-1", objective="write tests", constraints=["no network"]
    )

    service_b = LLMAgentTaskContextService(store=JsonTaskContextStore(path))
    fetched = service_b.get(task_context.task_id)

    assert fetched.objective == "write tests"
    assert fetched.constraints == ["no network"]


# --- scope and agent isolation ----------------------------------------------------


def test_scope_and_agent_isolation():
    service = _service()

    task_a = service.create(agent_id="agent-1", scope_id="scope-1", objective="task A")
    task_b = service.create(agent_id="agent-2", scope_id="scope-2", objective="task B")

    service.update(task_a.task_id, {"objective": "task A revised"})

    assert service.get(task_a.task_id).objective == "task A revised"
    assert service.get(task_b.task_id).agent_id == "agent-2"
    assert service.get(task_b.task_id).scope_id == "scope-2"
    assert service.get(task_b.task_id).objective == "task B"


def test_same_agent_different_scopes_are_independent():
    service = _service()

    task_a = service.create(agent_id="agent-1", scope_id="scope-1", objective="scope 1 work")
    task_b = service.create(agent_id="agent-1", scope_id="scope-2", objective="scope 2 work")

    service.update(task_a.task_id, {"inputs": {"only": "scope-1"}})

    assert service.get(task_a.task_id).inputs == {"only": "scope-1"}
    assert service.get(task_b.task_id).inputs == {}


# --- context provenance preserved -------------------------------------------------


def test_provenance_auto_derived_for_context_with_id():
    service = _service()
    context = _project_context().to_dict()

    task_context = service.create(
        agent_id="agent-1", scope_id="scope-1", objective="use context", relevant_context=[context]
    )

    assert len(task_context.provenance) == 1
    entry = task_context.provenance[0]
    assert entry.context_id == context["context_id"]
    assert entry.source_type == "project_context"
    assert entry.source_id == context["context_id"]
    assert entry.excerpt


def test_provenance_preserved_after_relevant_context_replaced():
    service = _service()
    first = _project_context(content="first fact").to_dict()
    second = _project_context(content="second fact").to_dict()

    task_context = service.create(
        agent_id="agent-1", scope_id="scope-1", objective="use context", relevant_context=[first]
    )
    first_provenance_ids = {entry.provenance_id for entry in task_context.provenance}

    updated = service.update(task_context.task_id, {"relevant_context": [second]})

    assert updated.relevant_context == [second]
    provenance_context_ids = {entry.context_id for entry in updated.provenance}
    # both the dropped-from-view "first" context and the new "second" context
    # are still traceable in the append-only provenance trail
    assert first["context_id"] in provenance_context_ids
    assert second["context_id"] in provenance_context_ids
    assert first_provenance_ids <= {entry.provenance_id for entry in updated.provenance}


def test_provenance_not_duplicated_for_repeated_context():
    service = _service()
    context = _project_context().to_dict()

    task_context = service.create(
        agent_id="agent-1", scope_id="scope-1", objective="use context", relevant_context=[context]
    )
    updated = service.update(task_context.task_id, {"relevant_context": [context]})

    assert len(updated.provenance) == 1


def test_explicit_provenance_is_validated_and_stored():
    service = _service()

    task_context = service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="use external context",
        provenance=[
            {
                "context_id": "ctx-external-1",
                "source_type": "external",
                "source_id": "https://example.com/doc",
                "excerpt": "an external document",
            }
        ],
    )

    assert len(task_context.provenance) == 1
    assert task_context.provenance[0].source_type == "external"


def test_invalid_provenance_source_type_rejected():
    service = _service()
    with pytest.raises(InvalidTaskContextError):
        service.create(
            agent_id="agent-1",
            scope_id="scope-1",
            objective="x",
            provenance=[
                {
                    "context_id": "ctx-1",
                    "source_type": "not-a-real-source-type",
                    "source_id": "src-1",
                    "excerpt": "excerpt",
                }
            ],
        )


# --- snapshot is immutable ---------------------------------------------------------


def test_snapshot_is_immutable_and_frozen():
    service = _service()
    task_context = service.create(
        agent_id="agent-1", scope_id="scope-1", objective="snapshot me", constraints=["c1"]
    )

    snapshot = service.snapshot(task_context.task_id)

    assert isinstance(snapshot, LLMAgentTaskContextSnapshot)
    assert snapshot.objective == "snapshot me"
    assert isinstance(snapshot.constraints, tuple)
    assert isinstance(snapshot.relevant_context, tuple)
    assert isinstance(snapshot.provenance, tuple)

    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.objective = "changed"


def test_snapshot_unaffected_by_later_updates():
    service = _service()
    task_context = service.create(
        agent_id="agent-1", scope_id="scope-1", objective="original objective", inputs={"k": "v"}
    )

    snapshot = service.snapshot(task_context.task_id)
    service.update(task_context.task_id, {"objective": "changed objective", "inputs": {"k": "changed"}})

    assert snapshot.objective == "original objective"
    assert snapshot.inputs["k"] == "v"
    assert service.get(task_context.task_id).objective == "changed objective"


def test_snapshot_unknown_task_raises():
    service = _service()
    with pytest.raises(UnknownTaskContextError):
        service.snapshot("missing-task")


# --- updates retain unaffected fields -----------------------------------------------


def test_update_retains_unaffected_fields():
    service = _service()
    task_context = service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="original",
        constraints=["c1"],
        inputs={"k": "v"},
    )

    updated = service.update(task_context.task_id, {"objective": "revised"})

    assert updated.objective == "revised"
    assert updated.constraints == ["c1"]
    assert updated.inputs == {"k": "v"}
    assert updated.task_id == task_context.task_id
    assert updated.agent_id == task_context.agent_id
    assert updated.scope_id == task_context.scope_id
    assert updated.created_at == task_context.created_at


def test_update_cannot_change_identity_fields():
    service = _service()
    task_context = service.create(agent_id="agent-1", scope_id="scope-1", objective="x")

    with pytest.raises(InvalidTaskContextError):
        service.update(task_context.task_id, {"agent_id": "agent-2"})
    with pytest.raises(InvalidTaskContextError):
        service.update(task_context.task_id, {"scope_id": "scope-2"})
    with pytest.raises(InvalidTaskContextError):
        service.update(task_context.task_id, {"task_id": "other"})
    with pytest.raises(InvalidTaskContextError):
        service.update(task_context.task_id, {"created_at": "2020-01-01T00:00:00+00:00"})


def test_update_rejects_unknown_fields():
    service = _service()
    task_context = service.create(agent_id="agent-1", scope_id="scope-1", objective="x")

    with pytest.raises(InvalidTaskContextError):
        service.update(task_context.task_id, {"not_a_real_field": 1})


def test_update_rejects_non_dict_changes():
    service = _service()
    task_context = service.create(agent_id="agent-1", scope_id="scope-1", objective="x")

    with pytest.raises(InvalidTaskContextError):
        service.update(task_context.task_id, ["not", "a", "dict"])


# --- invalid task context is rejected ------------------------------------------------


def test_create_rejects_missing_identity_fields():
    service = _service()

    with pytest.raises(InvalidTaskContextError):
        service.create(agent_id="", scope_id="scope-1", objective="x")
    with pytest.raises(InvalidTaskContextError):
        service.create(agent_id="agent-1", scope_id="", objective="x")
    with pytest.raises(InvalidTaskContextError):
        service.create(agent_id="agent-1", scope_id="scope-1", objective="")


def test_create_rejects_malformed_constraints_and_inputs():
    service = _service()

    with pytest.raises(InvalidTaskContextError):
        service.create(agent_id="agent-1", scope_id="scope-1", objective="x", constraints="not-a-list")
    with pytest.raises(InvalidTaskContextError):
        service.create(agent_id="agent-1", scope_id="scope-1", objective="x", inputs="not-a-dict")
    with pytest.raises(InvalidTaskContextError):
        service.create(agent_id="agent-1", scope_id="scope-1", objective="x", relevant_context="not-a-list")
    with pytest.raises(InvalidTaskContextError):
        service.create(agent_id="agent-1", scope_id="scope-1", objective="x", relevant_context=[123])


def test_create_rejects_blank_explicit_task_id():
    service = _service()
    with pytest.raises(InvalidTaskContextError):
        service.create(agent_id="agent-1", scope_id="scope-1", objective="x", task_id="")


# --- select_relevant_context reuses existing selection/compaction infra -------------


def test_select_relevant_context_reuses_selection_and_compaction():
    service = _service()
    on_topic = _project_context(content="notebook dependency graph analysis")
    off_topic = _project_context(content="unrelated grocery list")

    selected = service.select_relevant_context(
        [on_topic, off_topic], objective="analyze the notebook dependency graph", token_budget=1000
    )

    assert any(entry["context_id"] == on_topic.context_id for entry in selected)

    task_context = service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="analyze the notebook dependency graph",
        relevant_context=selected,
    )
    assert any(entry.context_id == on_topic.context_id for entry in task_context.provenance)


def test_select_relevant_context_respects_token_budget():
    service = _service()
    contexts = [_project_context(content="x" * 4000, context_type="summary") for _ in range(3)]

    selected = service.select_relevant_context(contexts, objective="x", token_budget=100)

    total_tokens = sum(len(entry["content"]) for entry in selected)
    assert total_tokens <= 100 * 4 + 200  # generous slack for the estimator's rounding
