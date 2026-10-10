import dataclasses

import pytest

from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_context_budgeting import LLMAgentTaskContextBudgeter
from backend.agent_task_context_packaging import LLMAgentTaskContextPackager
from backend.agent_task_context_provenance import (
    ContextProvenanceRecord,
    InvalidProvenanceRecordError,
    JsonProvenanceRecordStore,
    LLMAgentTaskContextProvenanceService,
    UnknownProvenanceRecordError,
    UnknownProvenanceTraceError,
)
from backend.agent_task_context_resolution import ResolvedAgentTaskContext
from backend.llm.context_provenance import LLMContextProvenance
from backend.llm.project_context import LLMProjectContextService


def _task_context(relevant_context=None):
    service = LLMAgentTaskContextService()
    return service.create(
        agent_id="agent-1", scope_id="scope-1", objective="analyze the notebook", relevant_context=relevant_context or []
    )


def _project_context_dict(content, context_id=None):
    service = LLMProjectContextService()
    context = service.create("scope-1", "fact", content)
    if context_id is not None:
        context.context_id = context_id
    return context.to_dict()


def _resolved(task_context, selected_context, resolution_reasons=None, excluded_context=None, provenance=None):
    return ResolvedAgentTaskContext(
        task_id=task_context.task_id,
        agent_id=task_context.agent_id,
        scope_id=task_context.scope_id,
        task_context=task_context,
        selected_context=selected_context,
        selected_memories=[],
        excluded_context=excluded_context or [],
        provenance=provenance if provenance is not None else list(task_context.provenance),
        resolution_reasons=resolution_reasons or {},
    )


def _pipeline(task_context, selected_context, resolution_reasons=None, excluded_context=None, limits=None, provenance=None):
    resolved = _resolved(
        task_context,
        selected_context,
        resolution_reasons=resolution_reasons,
        excluded_context=excluded_context,
        provenance=provenance,
    )
    budgeted = LLMAgentTaskContextBudgeter().budget(resolved, limits or {"token_budget": 10_000})
    package = LLMAgentTaskContextPackager().package(task_context, budgeted)
    return resolved, budgeted, package


def _service(store=None):
    return LLMAgentTaskContextProvenanceService(store=store)


# --- provenance is recorded for packaged context --------------------------------------------


def test_provenance_is_recorded_for_packaged_context():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    resolved, budgeted, package = _pipeline(task_context, [entry], resolution_reasons={entry["context_id"]: "relevant"})

    record = _service().record(task_context.task_id, package, source={"resolved": resolved, "budgeted": budgeted})

    assert isinstance(record, ContextProvenanceRecord)
    assert record.task_id == task_context.task_id
    ids = {e.source_id for e in record.entries}
    assert entry["context_id"] in ids
    matching = next(e for e in record.entries if e.source_id == entry["context_id"])
    assert matching.included is True
    assert matching.selection_reason == "relevant"


def test_record_without_source_still_succeeds_with_thinner_trail():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    _resolved_unused, _budgeted_unused, package = _pipeline(task_context, [entry])

    record = _service().record(task_context.task_id, package)

    ids = {e.source_id for e in record.entries}
    assert entry["context_id"] in ids
    matching = next(e for e in record.entries if e.source_id == entry["context_id"])
    assert matching.selection_reason is None
    assert matching.transformation is None
    assert matching.included is True


# --- source/version information survives transformations ------------------------------------


def test_source_version_survives_into_record_and_trace():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    provenance = [
        LLMContextProvenance(
            context_id=entry["context_id"], source_type="project_context", source_id=entry["context_id"], excerpt="x"
        )
    ]
    resolved, budgeted, package = _pipeline(task_context, [entry], provenance=provenance)

    # give the packaged provenance record an explicit source_version
    # (package.provenance holds Commit #4's own plain-dict rendering)
    versioned_provenance = [
        {**p, "source_version": 3} if p["context_id"] == entry["context_id"] else p for p in package.provenance
    ]
    package = dataclasses.replace(package, provenance=versioned_provenance)

    service = _service()
    service.record(task_context.task_id, package, source={"resolved": resolved, "budgeted": budgeted})
    trace = service.trace(task_context.task_id, entry["context_id"])

    assert trace.source_version == 3
    assert trace.source.context_id == entry["context_id"]


# --- inclusion/exclusion reasons are preserved -------------------------------------------------


def test_excluded_source_reason_is_preserved_even_though_not_packaged():
    survivor = _project_context_dict("survivor content")
    task_context = _task_context()
    resolved, budgeted, package = _pipeline(
        task_context,
        [survivor],
        resolution_reasons={
            survivor["context_id"]: "included: relevant",
            "excluded-ctx": "excluded as irrelevant: no matching terms",
        },
    )

    record = _service().record(task_context.task_id, package, source={"resolved": resolved, "budgeted": budgeted})

    entry = next(e for e in record.entries if e.source_id == "excluded-ctx")
    assert entry.included is False
    assert "excluded" in entry.selection_reason


def test_dropped_by_budgeting_reason_is_preserved():
    oversized = _project_context_dict("filler content " * 300, context_id="oversized-1")
    task_context = _task_context()
    resolved, budgeted, package = _pipeline(task_context, [oversized], limits={"token_budget": 1})
    assert budgeted.dropped_context  # sanity: it really was dropped

    record = _service().record(task_context.task_id, package, source={"resolved": resolved, "budgeted": budgeted})

    entry = next(e for e in record.entries if e.source_id == "oversized-1")
    assert entry.included is False
    assert "dropped" in entry.transformation


# --- trace returns the expected lineage -------------------------------------------------------


def test_trace_returns_expected_lineage():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    provenance = [
        LLMContextProvenance(
            context_id=entry["context_id"], source_type="project_context", source_id=entry["context_id"], excerpt="x"
        )
    ]
    resolved, budgeted, package = _pipeline(
        task_context, [entry], resolution_reasons={entry["context_id"]: "included: relevant"}, provenance=provenance
    )

    service = _service()
    service.record(task_context.task_id, package, source={"resolved": resolved, "budgeted": budgeted})
    trace = service.trace(task_context.task_id, entry["context_id"])

    assert trace.included is True
    assert trace.selection_reason == "included: relevant"
    assert trace.transformation is not None
    assert trace.source.context_id == entry["context_id"]


def test_trace_reflects_most_recent_record():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    _resolved1, _budgeted1, package1 = _pipeline(
        task_context, [entry], resolution_reasons={entry["context_id"]: "first reason"}
    )
    _resolved2, _budgeted2, package2 = _pipeline(
        task_context, [entry], resolution_reasons={entry["context_id"]: "second reason"}
    )

    service = _service()
    service.record(task_context.task_id, package1, source={"resolved": _resolved1})
    service.record(task_context.task_id, package2, source={"resolved": _resolved2})

    trace = service.trace(task_context.task_id, entry["context_id"])
    assert trace.selection_reason == "second reason"
    assert len(service.get(task_context.task_id)) == 2


def test_unknown_task_id_trace_raises():
    with pytest.raises(UnknownProvenanceRecordError):
        _service().trace("missing-task", "ctx-1")


def test_unknown_source_id_trace_raises():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    _r, _b, package = _pipeline(task_context, [entry])
    service = _service()
    service.record(task_context.task_id, package)

    with pytest.raises(UnknownProvenanceTraceError):
        service.trace(task_context.task_id, "never-seen-id")


# --- records are immutable ----------------------------------------------------------------------


def test_records_are_immutable():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    _r, _b, package = _pipeline(task_context, [entry])
    record = _service().record(task_context.task_id, package)

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.task_id = "other"
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.entries[0].included = False


def test_get_returns_new_records_across_calls_never_mutated():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    _r, _b, package = _pipeline(task_context, [entry])
    service = _service()
    service.record(task_context.task_id, package)

    first = service.get(task_context.task_id)
    second = service.get(task_context.task_id)
    assert first == second
    assert first is not second


def test_json_store_round_trips_across_service_instances(tmp_path):
    path = tmp_path / "provenance.json"
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    _r, _b, package = _pipeline(task_context, [entry])

    service_a = _service(store=JsonProvenanceRecordStore(path))
    service_a.record(task_context.task_id, package)

    service_b = _service(store=JsonProvenanceRecordStore(path))
    records = service_b.get(task_context.task_id)

    assert len(records) == 1
    assert {e.source_id for e in records[0].entries} == {entry["context_id"]}


# --- sensitive payloads are not duplicated ------------------------------------------------------


def test_raw_content_is_never_persisted_in_the_record():
    entry = _project_context_dict("this is the actual sensitive body text")
    task_context = _task_context()
    _r, _b, package = _pipeline(task_context, [entry])

    record = _service().record(task_context.task_id, package)
    serialized = record.to_dict()

    assert "this is the actual sensitive body text" not in str(serialized)
    for entry_dict in serialized["entries"]:
        assert "content" not in entry_dict


def test_secret_looking_excerpt_is_not_double_stored():
    entry = _project_context_dict("normal content")
    task_context = _task_context()
    provenance = [
        LLMContextProvenance(
            context_id=entry["context_id"], source_type="project_context", source_id=entry["context_id"], excerpt="an excerpt"
        )
    ]
    resolved, budgeted, package = _pipeline(task_context, [entry])
    package = dataclasses.replace(package, provenance=provenance)

    record = _service().record(task_context.task_id, package)
    matching = next(e for e in record.entries if e.source_id == entry["context_id"])
    assert matching.source.excerpt == "an excerpt"
    # exactly one provenance record for this source, not duplicated
    assert sum(1 for e in record.entries if e.source_id == entry["context_id"]) == 1


# --- invalid input is rejected --------------------------------------------------------------------


def test_mismatched_task_id_and_package_rejected():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    _r, _b, package = _pipeline(task_context, [entry])

    with pytest.raises(InvalidProvenanceRecordError):
        _service().record("some-other-task-id", package)


def test_mismatched_resolved_source_rejected():
    entry = _project_context_dict("hello world")
    task_context_a = _task_context()
    task_context_b = _task_context()
    resolved_b, _budgeted_b, _package_b = _pipeline(task_context_b, [entry])
    _r_a, _b_a, package_a = _pipeline(task_context_a, [entry])

    with pytest.raises(InvalidProvenanceRecordError):
        _service().record(task_context_a.task_id, package_a, source={"resolved": resolved_b})


def test_invalid_package_type_rejected():
    with pytest.raises(InvalidProvenanceRecordError):
        _service().record("task-1", "not-a-package")


def test_non_dict_source_rejected():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    _r, _b, package = _pipeline(task_context, [entry])

    with pytest.raises(InvalidProvenanceRecordError):
        _service().record(task_context.task_id, package, source="not-a-dict")
