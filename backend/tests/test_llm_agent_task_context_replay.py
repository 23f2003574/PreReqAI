import pytest

from backend.agent_task_context import LLMAgentTaskContextService, UnknownTaskContextError
from backend.agent_task_context_replay import (
    CrossTaskReplayError,
    InvalidContextReplayError,
    LLMAgentTaskContextReplayService,
    TaskContextReplayResult,
)
from backend.agent_task_context_resolution import LLMAgentTaskContextResolver
from backend.agent_task_context_snapshots import (
    LLMAgentTaskContextSnapshotService,
    TaskContextSnapshot,
    UnknownTaskContextSnapshotError,
)
from backend.llm.context_provenance import LLMContextProvenance
from backend.llm.project_context import LLMProjectContextService


def _stack():
    project_context_service = LLMProjectContextService()
    task_context_service = LLMAgentTaskContextService()
    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    snapshot_service = LLMAgentTaskContextSnapshotService(task_context_service, resolver)
    replay_service = LLMAgentTaskContextReplayService(task_context_service, snapshot_service)
    return project_context_service, task_context_service, snapshot_service, replay_service


# --- valid snapshot reproduces identical context ------------------------------------------------


def test_valid_snapshot_reproduces_identical_context():
    project_context_service, task_context_service, snapshot_service, replay_service = _stack()
    on_topic = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)

    result = replay_service.replay(task_context.task_id, snapshot.snapshot_id)

    assert isinstance(result, TaskContextReplayResult)
    assert result.snapshot_id == snapshot.snapshot_id
    assert result.task_id == task_context.task_id
    assert result.context_version == snapshot.context_version
    assert result.context == snapshot.resolved_context["context"]
    assert result.reproducible is True
    assert result.differences == []
    context_ids = {entry["context_id"] for entry in result.context}
    assert on_topic.context_id in context_ids


# --- historical snapshot remains independent of current context --------------------------------


def test_replay_is_independent_of_later_task_changes():
    project_context_service, task_context_service, snapshot_service, replay_service = _stack()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)
    original_context = list(snapshot.resolved_context["context"])

    # mutate the live task context after the snapshot was taken
    task_context_service.update(
        task_context.task_id,
        {"relevant_context": [{"context_id": "unrelated-new", "content": "brand new", "context_type": "fact", "scope_id": "scope-1"}]},
    )
    project_context_service.create("scope-1", "fact", "another notebook dependency graph analysis note")

    result = replay_service.replay(task_context.task_id, snapshot.snapshot_id)

    assert result.context == original_context
    replayed_ids = {entry["context_id"] for entry in result.context}
    assert "unrelated-new" not in replayed_ids


# --- missing historical data is reported ----------------------------------------------------------


def test_missing_resolved_context_is_reported():
    _project_context_service, task_context_service, snapshot_service, replay_service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")

    corrupted = TaskContextSnapshot(
        task_id=task_context.task_id,
        scope_id="scope-1",
        context_version=1,
        resolved_context={},  # missing "context" key entirely
        provenance=(),
    )
    snapshot_service.store.save(corrupted)

    result = replay_service.replay(task_context.task_id, corrupted.snapshot_id)

    assert result.reproducible is False
    assert any("resolved_context" in difference for difference in result.differences)
    assert result.context == []


# --- provenance is preserved ------------------------------------------------------------------------


def test_provenance_is_preserved():
    project_context_service, task_context_service, snapshot_service, replay_service = _stack()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)
    assert snapshot.provenance  # sanity

    result = replay_service.replay(task_context.task_id, snapshot.snapshot_id)

    assert list(result.provenance) == list(snapshot.provenance)


# --- corrupted/version-mismatched data is detected ----------------------------------------------


def test_corrupted_provenance_is_detected():
    _project_context_service, task_context_service, snapshot_service, replay_service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")

    bad_provenance = LLMContextProvenance(
        context_id="ctx-1", source_type="not-a-real-type", source_id="ctx-1", excerpt="x"
    )
    corrupted = TaskContextSnapshot(
        task_id=task_context.task_id,
        scope_id="scope-1",
        context_version=1,
        resolved_context={
            "context": [{"context_id": "ctx-1", "content": "some content", "context_type": "fact", "scope_id": "scope-1"}],
            "memories": [],
        },
        provenance=(bad_provenance,),
    )
    snapshot_service.store.save(corrupted)

    result = replay_service.replay(task_context.task_id, corrupted.snapshot_id)

    assert result.reproducible is False
    assert result.differences


def test_missing_provenance_for_a_context_entry_is_detected():
    _project_context_service, task_context_service, snapshot_service, replay_service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")

    corrupted = TaskContextSnapshot(
        task_id=task_context.task_id,
        scope_id="scope-1",
        context_version=1,
        resolved_context={
            "context": [{"context_id": "ctx-1", "content": "some content", "context_type": "fact", "scope_id": "scope-1"}],
            "memories": [],
        },
        provenance=(),  # no provenance at all for ctx-1
    )
    snapshot_service.store.save(corrupted)

    result = replay_service.replay(task_context.task_id, corrupted.snapshot_id)

    assert result.reproducible is False
    assert result.differences


# --- replay performs no mutations or execution ----------------------------------------------------


def test_replay_is_side_effect_free():
    project_context_service, task_context_service, snapshot_service, replay_service = _stack()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)

    before_task = task_context_service.get(task_context.task_id)
    before_project = project_context_service.get(context.context_id)
    before_snapshot = snapshot_service.get(snapshot.snapshot_id)

    replay_service.replay(task_context.task_id, snapshot.snapshot_id)

    assert task_context_service.get(task_context.task_id) == before_task
    assert project_context_service.get(context.context_id) == before_project
    assert snapshot_service.get(snapshot.snapshot_id) == before_snapshot
    assert snapshot_service.list(task_context.task_id) == [snapshot]  # no new snapshot created


def test_replay_is_deterministic():
    project_context_service, task_context_service, snapshot_service, replay_service = _stack()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)

    first = replay_service.replay(task_context.task_id, snapshot.snapshot_id)
    second = replay_service.replay(task_context.task_id, snapshot.snapshot_id)

    assert first == second


# --- cross-task / invalid input ----------------------------------------------------------------------


def test_cross_task_replay_is_rejected():
    _project_context_service, task_context_service, snapshot_service, replay_service = _stack()
    task_a = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="task A")
    task_b = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="task B")
    snapshot_a = snapshot_service.create(task_a.task_id)

    with pytest.raises(CrossTaskReplayError):
        replay_service.replay(task_b.task_id, snapshot_a.snapshot_id)


def test_invalid_identifiers_rejected():
    _p, _t, _s, replay_service = _stack()
    with pytest.raises(InvalidContextReplayError):
        replay_service.replay("", "snapshot-1")
    with pytest.raises(InvalidContextReplayError):
        replay_service.replay("task-1", "")


def test_unknown_snapshot_propagates():
    _p, task_context_service, _s, replay_service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    with pytest.raises(UnknownTaskContextSnapshotError):
        replay_service.replay(task_context.task_id, "missing-snapshot")


def test_unknown_task_propagates():
    _project_context_service, task_context_service, snapshot_service, replay_service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    snapshot = snapshot_service.create(task_context.task_id)

    with pytest.raises(UnknownTaskContextError):
        replay_service.replay("missing-task", snapshot.snapshot_id)
