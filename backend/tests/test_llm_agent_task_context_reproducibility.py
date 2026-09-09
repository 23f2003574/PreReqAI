import dataclasses

import pytest

from backend.agent_task_context import LLMAgentTaskContextService, UnknownTaskContextError
from backend.agent_task_context_replay import CrossTaskReplayError, LLMAgentTaskContextReplayService
from backend.agent_task_context_resolution import LLMAgentTaskContextResolver
from backend.agent_task_context_reproducibility import (
    BLOCKED,
    InvalidReproducibilityAssessmentError,
    LLMAgentTaskContextReproducibilityService,
    REPRODUCIBLE,
    TaskContextReproducibilityResult,
)
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
    service = LLMAgentTaskContextReproducibilityService(
        task_context_service, snapshot_service, project_context_service, replay_service=replay_service
    )
    return project_context_service, task_context_service, snapshot_service, replay_service, service


class _StubReplayService:
    """Wraps a real replay service but overrides .context, to isolate the
    "expected vs replayed" comparison without needing a self-contradictory
    real snapshot."""

    def __init__(self, real_replay_service, override_context):
        self._real = real_replay_service
        self._override_context = override_context

    def replay(self, task_id, snapshot_id):
        real_result = self._real.replay(task_id, snapshot_id)
        return dataclasses.replace(real_result, context=self._override_context)


# --- exact snapshot replay -> reproducible -------------------------------------------------------


def test_exact_snapshot_replay_is_reproducible():
    project_context_service, task_context_service, snapshot_service, _replay, service = _stack()
    on_topic = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)

    result = service.assess(task_context.task_id, snapshot.snapshot_id)

    assert isinstance(result, TaskContextReproducibilityResult)
    assert result.status == REPRODUCIBLE
    assert result.reproducible is True
    assert result.blockers == []
    assert result.differences == []
    assert result.provenance_complete is True
    assert result.source_versions_available is True
    assert result.integrity_valid is True
    assert result.expected_context == result.replayed_context
    context_ids = {entry["context_id"] for entry in result.expected_context}
    assert on_topic.context_id in context_ids


# --- missing source version -> non-reproducible with blocker -------------------------------------


def test_missing_source_is_non_reproducible_with_blocker():
    project_context_service, task_context_service, snapshot_service, _replay, service = _stack()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="notebook dependency graph analysis",
        relevant_context=[context.to_dict()],
    )
    snapshot = snapshot_service.create(task_context.task_id)

    project_context_service.delete(context.context_id)

    result = service.assess(task_context.task_id, snapshot.snapshot_id)

    assert result.reproducible is False
    assert result.source_versions_available is False
    assert any(context.context_id in blocker for blocker in result.blockers)


# --- provenance gap -> non-reproducible with explicit gap -----------------------------------------


def test_provenance_gap_is_reported_explicitly():
    _project_context_service, task_context_service, snapshot_service, _replay, service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")

    corrupted = TaskContextSnapshot(
        task_id=task_context.task_id,
        scope_id="scope-1",
        context_version=1,
        resolved_context={
            "context": [{"context_id": "ctx-1", "content": "some content", "context_type": "fact", "scope_id": "scope-1"}],
            "memories": [],
        },
        provenance=(),  # no provenance for ctx-1 at all
    )
    snapshot_service.store.save(corrupted)

    result = service.assess(task_context.task_id, corrupted.snapshot_id)

    assert result.reproducible is False
    assert result.provenance_complete is False
    assert result.blockers  # the gap is surfaced, not silently ignored


# --- context difference -> non-reproducible with diff details -------------------------------------


def test_context_difference_between_expected_and_replayed_is_detected():
    project_context_service, task_context_service, snapshot_service, real_replay_service, _service = _stack()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)
    assert snapshot.resolved_context["context"]  # sanity: there is real context to diverge from

    stub_replay = _StubReplayService(real_replay_service, override_context=[])
    service = LLMAgentTaskContextReproducibilityService(
        task_context_service, snapshot_service, project_context_service, replay_service=stub_replay
    )

    result = service.assess(task_context.task_id, snapshot.snapshot_id)

    assert result.reproducible is False
    assert result.differences
    assert result.replayed_context == []
    assert result.expected_context != result.replayed_context


# --- integrity failure -> blocked -------------------------------------------------------------------


def test_integrity_failure_is_blocked():
    _project_context_service, task_context_service, snapshot_service, _replay, service = _stack()
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

    result = service.assess(task_context.task_id, corrupted.snapshot_id)

    assert result.status == BLOCKED
    assert result.reproducible is False
    assert result.integrity_valid is False
    assert result.blockers


# --- successful assessment performs no mutation --------------------------------------------------


def test_assessment_is_side_effect_free():
    project_context_service, task_context_service, snapshot_service, _replay, service = _stack()
    context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)

    before_task = task_context_service.get(task_context.task_id)
    before_project = project_context_service.get(context.context_id)
    before_history = snapshot_service.list(task_context.task_id)

    service.assess(task_context.task_id, snapshot.snapshot_id)

    assert task_context_service.get(task_context.task_id) == before_task
    assert project_context_service.get(context.context_id) == before_project
    assert snapshot_service.list(task_context.task_id) == before_history


# --- repeated assessment produces the same result -------------------------------------------------


def test_repeated_assessment_is_deterministic():
    project_context_service, task_context_service, snapshot_service, _replay, service = _stack()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )
    snapshot = snapshot_service.create(task_context.task_id)

    first = service.assess(task_context.task_id, snapshot.snapshot_id)
    second = service.assess(task_context.task_id, snapshot.snapshot_id)

    assert first == second


# --- invalid input / cross-task -------------------------------------------------------------------


def test_invalid_identifiers_rejected():
    _p, _t, _s, _r, service = _stack()
    with pytest.raises(InvalidReproducibilityAssessmentError):
        service.assess("", "snapshot-1")
    with pytest.raises(InvalidReproducibilityAssessmentError):
        service.assess("task-1", "")


def test_unknown_snapshot_propagates():
    _p, task_context_service, _s, _r, service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    with pytest.raises(UnknownTaskContextSnapshotError):
        service.assess(task_context.task_id, "missing-snapshot")


def test_unknown_task_propagates():
    _p, task_context_service, snapshot_service, _r, service = _stack()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    snapshot = snapshot_service.create(task_context.task_id)
    with pytest.raises(UnknownTaskContextError):
        service.assess("missing-task", snapshot.snapshot_id)


def test_cross_task_snapshot_is_rejected():
    _p, task_context_service, snapshot_service, _r, service = _stack()
    task_a = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="task A")
    task_b = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="task B")
    snapshot_a = snapshot_service.create(task_a.task_id)

    with pytest.raises(CrossTaskReplayError):
        service.assess(task_b.task_id, snapshot_a.snapshot_id)
