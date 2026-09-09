import dataclasses

import pytest

from backend.agent_task_context import LLMAgentTaskContextService, UnknownTaskContextError
from backend.agent_task_context_resolution import LLMAgentTaskContextResolver
from backend.agent_task_context_snapshots import (
    CrossTaskSnapshotError,
    JsonTaskContextSnapshotStore,
    LLMAgentTaskContextSnapshotService,
    TaskContextSnapshot,
    UnknownTaskContextSnapshotError,
)
from backend.llm.project_context import LLMProjectContextService


def _stack():
    project_context_service = LLMProjectContextService()
    task_context_service = LLMAgentTaskContextService()
    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    snapshot_service = LLMAgentTaskContextSnapshotService(task_context_service, resolver)
    return project_context_service, task_context_service, resolver, snapshot_service


# --- create/get/list snapshots ------------------------------------------------------------------


def test_create_get_list_lifecycle():
    project_context_service, task_context_service, resolver, snapshot_service = _stack()
    on_topic = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    snapshot = snapshot_service.create(task_context.task_id)

    assert isinstance(snapshot, TaskContextSnapshot)
    assert snapshot.task_id == task_context.task_id
    assert snapshot.scope_id == "scope-1"
    assert snapshot.context_version == 1
    context_ids = {entry["context_id"] for entry in snapshot.resolved_context["context"]}
    assert on_topic.context_id in context_ids

    fetched = snapshot_service.get(snapshot.snapshot_id)
    assert fetched == snapshot

    listed = snapshot_service.list(task_context.task_id)
    assert listed == [snapshot]


def test_second_create_bumps_context_version():
    _project_context_service, task_context_service, _resolver, snapshot_service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")

    first = snapshot_service.create(task_context.task_id)
    second = snapshot_service.create(task_context.task_id)

    assert first.context_version == 1
    assert second.context_version == 2
    assert snapshot_service.list(task_context.task_id) == [first, second]


def test_get_unknown_snapshot_raises():
    _p, _t, _r, snapshot_service = _stack()
    with pytest.raises(UnknownTaskContextSnapshotError):
        snapshot_service.get("missing-snapshot")


def test_create_unknown_task_raises():
    _p, _t, _r, snapshot_service = _stack()
    with pytest.raises(UnknownTaskContextError):
        snapshot_service.create("missing-task")


def test_json_store_round_trips_across_service_instances(tmp_path):
    path = tmp_path / "snapshots.json"
    project_context_service = LLMProjectContextService()
    task_context_service = LLMAgentTaskContextService()
    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")

    service_a = LLMAgentTaskContextSnapshotService(task_context_service, resolver, store=JsonTaskContextSnapshotStore(path))
    created = service_a.create(task_context.task_id)

    service_b = LLMAgentTaskContextSnapshotService(task_context_service, resolver, store=JsonTaskContextSnapshotStore(path))
    fetched = service_b.get(created.snapshot_id)

    assert fetched.task_id == task_context.task_id
    assert fetched.context_version == 1


# --- snapshot remains unchanged after task-context updates -------------------------------------


def test_snapshot_unaffected_by_later_task_context_updates():
    _project_context_service, task_context_service, _resolver, snapshot_service = _stack()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="original objective", inputs={"k": "v"}
    )

    snapshot = snapshot_service.create(task_context.task_id)

    task_context_service.update(task_context.task_id, {"objective": "changed objective", "inputs": {"k": "changed"}})

    refetched = snapshot_service.get(snapshot.snapshot_id)
    assert refetched.resolved_context == snapshot.resolved_context
    assert refetched.provenance == snapshot.provenance


def test_snapshot_fields_are_immutable():
    _project_context_service, task_context_service, _resolver, snapshot_service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    snapshot = snapshot_service.create(task_context.task_id)

    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.context_version = 99


# --- restore creates a new version / restored context matches the snapshot ---------------------


def test_restore_creates_a_new_version_and_matches_snapshot():
    project_context_service, task_context_service, resolver, snapshot_service = _stack()
    on_topic = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    snapshot = snapshot_service.create(task_context.task_id)
    assert snapshot_service.list(task_context.task_id) == [snapshot]

    restored = snapshot_service.restore(task_context.task_id, snapshot.snapshot_id)

    restored_ids = {entry["context_id"] for entry in restored.relevant_context}
    assert on_topic.context_id in restored_ids

    snapshot_history = snapshot_service.list(task_context.task_id)
    assert len(snapshot_history) == 2  # the original + the post-restore snapshot
    assert snapshot_history[-1].context_version == 2


def test_restore_matches_snapshot_content_exactly():
    project_context_service, task_context_service, resolver, snapshot_service = _stack()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)

    restored = snapshot_service.restore(task_context.task_id, snapshot.snapshot_id)

    assert restored.relevant_context == snapshot.resolved_context["context"]


# --- cross-task restoration is rejected ----------------------------------------------------------


def test_cross_task_restoration_is_rejected():
    _project_context_service, task_context_service, _resolver, snapshot_service = _stack()
    task_a = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="task A")
    task_b = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="task B")

    snapshot_a = snapshot_service.create(task_a.task_id)

    with pytest.raises(CrossTaskSnapshotError):
        snapshot_service.restore(task_b.task_id, snapshot_a.snapshot_id)


# --- provenance survives restoration -------------------------------------------------------------


def test_provenance_survives_restoration():
    project_context_service, task_context_service, resolver, snapshot_service = _stack()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)
    assert snapshot.provenance  # sanity: there is real provenance to preserve

    restored = snapshot_service.restore(task_context.task_id, snapshot.snapshot_id)

    restored_provenance_ids = {p.context_id for p in restored.provenance}
    snapshot_provenance_ids = {p.context_id for p in snapshot.provenance}
    assert snapshot_provenance_ids <= restored_provenance_ids


# --- no changes to underlying project context or agent memory -----------------------------------


def test_create_and_restore_do_not_mutate_project_context():
    project_context_service, task_context_service, resolver, snapshot_service = _stack()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    before = project_context_service.get(context.context_id)

    snapshot = snapshot_service.create(task_context.task_id)
    snapshot_service.restore(task_context.task_id, snapshot.snapshot_id)

    assert project_context_service.get(context.context_id) == before
