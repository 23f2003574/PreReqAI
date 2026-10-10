import pytest

from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_context_diff import (
    CrossTaskDiffError,
    InvalidTaskContextDiffError,
    LLMAgentTaskContextDiffService,
    TaskContextDiff,
    UnknownTaskContextVersionError,
)
from backend.agent_task_context_resolution import LLMAgentTaskContextResolver
from backend.agent_task_context_snapshots import (
    LLMAgentTaskContextSnapshotService,
    UnknownTaskContextSnapshotError,
)
from backend.llm.context_provenance import LLMContextProvenance
from backend.llm.project_context import LLMProjectContextService


def _stack():
    project_context_service = LLMProjectContextService()
    task_context_service = LLMAgentTaskContextService()
    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    snapshot_service = LLMAgentTaskContextSnapshotService(task_context_service, resolver)
    diff_service = LLMAgentTaskContextDiffService(snapshot_service)
    return project_context_service, task_context_service, snapshot_service, diff_service


# --- identical versions produce an empty diff --------------------------------------------------


def test_diffing_a_version_against_itself_is_empty():
    project_context_service, task_context_service, snapshot_service, diff_service = _stack()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot_service.create(task_context.task_id)

    result = diff_service.diff(task_context.task_id, 1, 1)

    assert isinstance(result, TaskContextDiff)
    assert result.added == []
    assert result.removed == []
    assert result.changed == []
    assert result.provenance_changes == []
    assert result.summary["added"] == 0
    assert result.summary["changed"] == 0


def test_two_snapshots_with_no_real_changes_produce_an_empty_diff():
    project_context_service, task_context_service, snapshot_service, diff_service = _stack()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot_service.create(task_context.task_id)
    snapshot_service.create(task_context.task_id)

    result = diff_service.diff(task_context.task_id, 1, 2)

    assert result.added == []
    assert result.removed == []
    assert result.changed == []
    assert result.unchanged  # the same source appears, unchanged, in both


# --- added/removed sources are detected -----------------------------------------------------------


def test_removed_source_is_detected():
    _project_context_service, task_context_service, snapshot_service, diff_service = _stack()
    entry_a = {"context_id": "ctx-a", "content": "a", "context_type": "fact", "scope_id": "scope-1"}
    entry_b = {"context_id": "ctx-b", "content": "b", "context_type": "fact", "scope_id": "scope-1"}
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="do work", relevant_context=[entry_a, entry_b]
    )
    snapshot_service.create(task_context.task_id)  # version 1: both present

    task_context_service.update(task_context.task_id, {"relevant_context": [entry_a]})
    snapshot_service.create(task_context.task_id)  # version 2: only ctx-a remains

    result = diff_service.diff(task_context.task_id, 1, 2)

    removed_ids = {item["context_id"] for item in result.removed}
    assert removed_ids == {"ctx-b"}
    assert result.added == []


def test_added_source_is_detected_via_resolver_retrieval():
    project_context_service, task_context_service, snapshot_service, diff_service = _stack()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot_service.create(task_context.task_id)  # version 1: nothing to retrieve yet

    on_topic = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    snapshot_service.create(task_context.task_id)  # version 2: now resolvable

    result = diff_service.diff(task_context.task_id, 1, 2)

    added_ids = {item["context_id"] for item in result.added}
    assert on_topic.context_id in added_ids
    assert result.removed == []


# --- changed source versions are detected --------------------------------------------------------


def test_changed_content_and_version_are_detected():
    _project_context_service, task_context_service, snapshot_service, diff_service = _stack()
    entry_v1 = {"context_id": "ctx-1", "content": "version 1 content", "context_type": "fact", "scope_id": "scope-1"}
    provenance_v1 = LLMContextProvenance(
        context_id="ctx-1", source_type="external", source_id="src-1", excerpt="v1", source_version=1
    )
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="do work", relevant_context=[entry_v1], provenance=[provenance_v1]
    )
    snapshot_service.create(task_context.task_id)  # version 1

    entry_v2 = {"context_id": "ctx-1", "content": "version 2 content", "context_type": "fact", "scope_id": "scope-1"}
    provenance_v2 = LLMContextProvenance(
        context_id="ctx-1", source_type="external", source_id="src-1", excerpt="v2", source_version=2
    )
    task_context_service.update(
        task_context.task_id, {"relevant_context": [entry_v2], "provenance": [provenance_v2]}
    )
    snapshot_service.create(task_context.task_id)  # version 2

    result = diff_service.diff(task_context.task_id, 1, 2)

    changed_ids = {item["context_id"] for item in result.changed}
    assert changed_ids == {"ctx-1"}
    matching = next(item for item in result.changed if item["context_id"] == "ctx-1")
    assert matching["from_entry"]["content"] == "version 1 content"
    assert matching["to_entry"]["content"] == "version 2 content"
    assert matching["from_provenance"].source_version == 1
    assert matching["to_provenance"].source_version == 2


# --- provenance changes are surfaced ---------------------------------------------------------------


def test_provenance_change_is_surfaced_even_without_content_change():
    _project_context_service, task_context_service, snapshot_service, diff_service = _stack()
    entry = {"context_id": "ctx-1", "content": "same content throughout", "context_type": "fact", "scope_id": "scope-1"}
    provenance_v1 = LLMContextProvenance(
        context_id="ctx-1", source_type="external", source_id="src-1", excerpt="original excerpt", source_version=1
    )
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="do work", relevant_context=[entry], provenance=[provenance_v1]
    )
    snapshot_service.create(task_context.task_id)  # version 1

    provenance_v2 = LLMContextProvenance(
        context_id="ctx-1", source_type="external", source_id="src-1", excerpt="revised excerpt", source_version=1
    )
    task_context_service.update(task_context.task_id, {"provenance": [provenance_v2]})
    snapshot_service.create(task_context.task_id)  # version 2: content unchanged, provenance excerpt changed

    result = diff_service.diff(task_context.task_id, 1, 2)

    assert result.changed == []  # content and source_version both unchanged
    provenance_change_ids = {item["context_id"] for item in result.provenance_changes}
    assert "ctx-1" in provenance_change_ids
    matching = next(item for item in result.provenance_changes if item["context_id"] == "ctx-1")
    assert matching["from_provenance"].excerpt == "original excerpt"
    assert matching["to_provenance"].excerpt == "revised excerpt"


# --- cross-task versions are rejected ---------------------------------------------------------------


def test_cross_task_snapshot_id_is_rejected():
    _p, task_context_service, snapshot_service, diff_service = _stack()
    task_a = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="task A")
    task_b = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="task B")
    snapshot_a = snapshot_service.create(task_a.task_id)
    snapshot_service.create(task_b.task_id)

    with pytest.raises(CrossTaskDiffError):
        diff_service.diff(task_b.task_id, snapshot_a.snapshot_id, 1)


def test_unknown_context_version_raises():
    _p, task_context_service, snapshot_service, diff_service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    snapshot_service.create(task_context.task_id)

    with pytest.raises(UnknownTaskContextVersionError):
        diff_service.diff(task_context.task_id, 1, 99)


def test_unknown_snapshot_id_propagates():
    _p, task_context_service, snapshot_service, diff_service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    snapshot_service.create(task_context.task_id)

    with pytest.raises(UnknownTaskContextSnapshotError):
        diff_service.diff(task_context.task_id, 1, "missing-snapshot")


# --- historical data remains unchanged -------------------------------------------------------------


def test_diff_is_side_effect_free():
    project_context_service, task_context_service, snapshot_service, diff_service = _stack()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot1 = snapshot_service.create(task_context.task_id)
    snapshot_service.create(task_context.task_id)

    before_task = task_context_service.get(task_context.task_id)
    before_project = project_context_service.get(context.context_id)
    before_history = snapshot_service.list(task_context.task_id)

    diff_service.diff(task_context.task_id, 1, 2)

    assert task_context_service.get(task_context.task_id) == before_task
    assert project_context_service.get(context.context_id) == before_project
    assert snapshot_service.list(task_context.task_id) == before_history
    assert snapshot_service.get(snapshot1.snapshot_id) == snapshot1


def test_diff_is_deterministic():
    project_context_service, task_context_service, snapshot_service, diff_service = _stack()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot_service.create(task_context.task_id)
    snapshot_service.create(task_context.task_id)

    first = diff_service.diff(task_context.task_id, 1, 2)
    second = diff_service.diff(task_context.task_id, 1, 2)

    assert first == second


# --- invalid input is rejected -----------------------------------------------------------------------


def test_invalid_task_id_rejected():
    _p, _t, _s, diff_service = _stack()
    with pytest.raises(InvalidTaskContextDiffError):
        diff_service.diff("", 1, 2)


def test_invalid_version_type_rejected():
    _p, task_context_service, snapshot_service, diff_service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    snapshot_service.create(task_context.task_id)

    with pytest.raises(InvalidTaskContextDiffError):
        diff_service.diff(task_context.task_id, 1.5, 2)
    with pytest.raises(InvalidTaskContextDiffError):
        diff_service.diff(task_context.task_id, 1, "")
