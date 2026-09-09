import pytest

from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_context_refresh import (
    ContextRefreshResult,
    InvalidContextRefreshError,
    LLMAgentTaskContextRefreshService,
)
from backend.agent_task_context_resolution import LLMAgentTaskContextResolver
from backend.llm.context_freshness import LLMContextFreshnessService
from backend.llm.context_provenance import LLMContextProvenanceService
from backend.llm.context_snapshot import LLMContextSnapshotService
from backend.llm.project_context import LLMProjectContextService


def _freshness_stack():
    project_context_service = LLMProjectContextService()
    provenance_service = LLMContextProvenanceService(project_context_service)
    snapshot_service = LLMContextSnapshotService()
    freshness_service = LLMContextFreshnessService(project_context_service, provenance_service, snapshot_service)
    return project_context_service, provenance_service, freshness_service


def _task_context_service():
    return LLMAgentTaskContextService()


# --- fresh context is handled without unnecessary replacement --------------------------------


def test_fresh_context_without_new_sources_is_a_no_op():
    project_context_service, provenance_service, freshness_service = _freshness_stack()
    context = project_context_service.create("scope-1", "fact", "still fresh content")
    recorded_provenance = provenance_service.attach(
        context.context_id,
        {"source_type": "project_context", "source_id": context.context_id, "excerpt": "x"},
    )

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="do work",
        relevant_context=[context.to_dict()],
        provenance=[recorded_provenance],
    )

    service = LLMAgentTaskContextRefreshService(task_context_service, freshness_service=freshness_service)
    result = service.refresh(task_context.task_id)

    assert isinstance(result, ContextRefreshResult)
    assert result.refreshed is False
    assert result.added_sources == []
    assert result.removed_sources == []
    assert result.stale_sources == []
    assert result.previous_context_version == result.new_context_version


# --- stale context is refreshed ----------------------------------------------------------------


def test_stale_context_is_removed_and_reported():
    project_context_service, provenance_service, freshness_service = _freshness_stack()
    context = project_context_service.create("scope-1", "fact", "original content")
    recorded_provenance = provenance_service.attach(
        context.context_id,
        {"source_type": "project_context", "source_id": context.context_id, "excerpt": "x"},
    )
    project_context_service.update(context.context_id, "revised content, after provenance was recorded")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="do work",
        relevant_context=[context.to_dict()],
        provenance=[recorded_provenance],
    )

    service = LLMAgentTaskContextRefreshService(task_context_service, freshness_service=freshness_service)
    result = service.refresh(task_context.task_id, reason="scheduled check")

    assert result.refreshed is True
    assert context.context_id in result.stale_sources
    assert any(entry["context_id"] == context.context_id for entry in result.removed_sources)
    assert result.reason == "scheduled check"

    refreshed_task = task_context_service.get(task_context.task_id)
    assert refreshed_task.relevant_context == []


def test_no_freshness_service_never_removes_anything():
    project_context_service, provenance_service, _unused = _freshness_stack()
    context = project_context_service.create("scope-1", "fact", "content")
    recorded_provenance = provenance_service.attach(
        context.context_id, {"source_type": "project_context", "source_id": context.context_id, "excerpt": "x"}
    )
    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="do work",
        relevant_context=[context.to_dict()],
        provenance=[recorded_provenance],
    )

    service = LLMAgentTaskContextRefreshService(task_context_service)
    result = service.refresh(task_context.task_id)

    assert result.refreshed is False
    assert result.stale_sources == []


# --- new relevant sources are incorporated ------------------------------------------------------


def test_new_relevant_source_is_added():
    project_context_service = LLMProjectContextService()
    on_topic = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    service = LLMAgentTaskContextRefreshService(task_context_service, resolver=resolver)

    result = service.refresh(task_context.task_id)

    assert result.refreshed is True
    added_ids = {entry["context_id"] for entry in result.added_sources}
    assert on_topic.context_id in added_ids

    refreshed_task = task_context_service.get(task_context.task_id)
    assert any(entry["context_id"] == on_topic.context_id for entry in refreshed_task.relevant_context)


def test_no_resolver_never_adds_anything():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")

    service = LLMAgentTaskContextRefreshService(task_context_service)
    result = service.refresh(task_context.task_id)

    assert result.refreshed is False
    assert result.added_sources == []


# --- mandatory task data survives refresh ---------------------------------------------------------


def test_mandatory_task_data_survives_refresh():
    project_context_service = LLMProjectContextService()
    project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="notebook dependency graph analysis",
        constraints=["read-only"],
        inputs={"notebook_id": "nb-1"},
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    service = LLMAgentTaskContextRefreshService(task_context_service, resolver=resolver)
    service.refresh(task_context.task_id)

    refreshed = task_context_service.get(task_context.task_id)
    assert refreshed.objective == "notebook dependency graph analysis"
    assert refreshed.constraints == ["read-only"]
    assert refreshed.inputs == {"notebook_id": "nb-1"}


# --- provenance survives refresh -------------------------------------------------------------------


def test_provenance_survives_refresh_for_both_removed_and_added_sources():
    project_context_service, provenance_service, freshness_service = _freshness_stack()
    stale_context = project_context_service.create("scope-1", "fact", "original content")
    recorded_provenance = provenance_service.attach(
        stale_context.context_id,
        {"source_type": "project_context", "source_id": stale_context.context_id, "excerpt": "x"},
    )
    project_context_service.update(stale_context.context_id, "revised, now stale")

    fresh_context = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="notebook dependency graph analysis",
        relevant_context=[stale_context.to_dict()],
        provenance=[recorded_provenance],
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    service = LLMAgentTaskContextRefreshService(task_context_service, resolver=resolver, freshness_service=freshness_service)
    service.refresh(task_context.task_id)

    refreshed = task_context_service.get(task_context.task_id)
    provenance_ids = {p.context_id for p in refreshed.provenance}
    assert stale_context.context_id in provenance_ids  # removed, but provenance preserved
    assert fresh_context.context_id in provenance_ids  # newly added, provenance derived


# --- previous context version remains readable ------------------------------------------------------


def test_previous_context_version_remains_readable_after_refresh():
    project_context_service = LLMProjectContextService()
    on_topic = project_context_service.create("scope-1", "fact", "notebook dependency graph analysis")

    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="notebook dependency graph analysis"
    )

    resolver = LLMAgentTaskContextResolver(task_context_service, project_context_service=project_context_service)
    service = LLMAgentTaskContextRefreshService(task_context_service, resolver=resolver)

    result = service.refresh(task_context.task_id)

    assert result.previous_context_version.relevant_context == ()
    assert result.new_context_version.relevant_context != ()
    assert result.previous_context_version.snapshot_id != result.new_context_version.snapshot_id


# --- refresh failure leaves the previous context intact ------------------------------------------------


class _ExplodingResolver:
    def resolve(self, *args, **kwargs):
        raise RuntimeError("boom: retrieval backend unavailable")


def test_refresh_failure_leaves_task_context_untouched():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(
        agent_id="agent-1", scope_id="scope-1", objective="do work", constraints=["c1"]
    )
    before = task_context_service.get(task_context.task_id)

    service = LLMAgentTaskContextRefreshService(task_context_service, resolver=_ExplodingResolver())

    with pytest.raises(RuntimeError):
        service.refresh(task_context.task_id)

    after = task_context_service.get(task_context.task_id)
    assert after == before


# --- invalid input is rejected -------------------------------------------------------------------------


def test_invalid_task_id_rejected():
    service = LLMAgentTaskContextRefreshService(_task_context_service())
    with pytest.raises(InvalidContextRefreshError):
        service.refresh("")


def test_invalid_reason_type_rejected():
    task_context_service = _task_context_service()
    task_context = task_context_service.create(agent_id="agent-1", scope_id="scope-1", objective="do work")
    service = LLMAgentTaskContextRefreshService(task_context_service)

    with pytest.raises(InvalidContextRefreshError):
        service.refresh(task_context.task_id, reason=123)


def test_unknown_task_id_propagates():
    from backend.agent_task_context import UnknownTaskContextError

    service = LLMAgentTaskContextRefreshService(_task_context_service())
    with pytest.raises(UnknownTaskContextError):
        service.refresh("missing-task")
