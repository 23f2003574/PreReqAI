import pytest

from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_context_budgeting import LLMAgentTaskContextBudgeter
from backend.agent_task_context_packaging import (
    AgentContextPackage,
    InvalidContextPackageError,
    LLMAgentTaskContextPackager,
)
from backend.agent_task_context_resolution import ResolvedAgentTaskContext
from backend.llm.context_injection import CONTEXT_ROLE
from backend.llm.project_context import LLMProjectContextService


def _task_context(relevant_context=None, inputs=None, constraints=None):
    service = LLMAgentTaskContextService()
    return service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="analyze the notebook",
        constraints=constraints if constraints is not None else ["read-only"],
        inputs=inputs if inputs is not None else {"notebook_id": "nb-1"},
        relevant_context=relevant_context or [],
    )


def _resolved(task_context, selected_context, selected_memories=None, provenance=None):
    return ResolvedAgentTaskContext(
        task_id=task_context.task_id,
        agent_id=task_context.agent_id,
        scope_id=task_context.scope_id,
        task_context=task_context,
        selected_context=selected_context,
        selected_memories=selected_memories or [],
        excluded_context=[],
        provenance=provenance if provenance is not None else list(task_context.provenance),
        resolution_reasons={},
    )


def _project_context_dict(content, context_type="fact", context_id=None):
    service = LLMProjectContextService()
    context = service.create("scope-1", context_type, content)
    if context_id is not None:
        context.context_id = context_id
    return context.to_dict()


def _budgeted(task_context, selected_context, limits=None, selected_memories=None, provenance=None):
    resolved = _resolved(task_context, selected_context, selected_memories=selected_memories, provenance=provenance)
    return LLMAgentTaskContextBudgeter().budget(resolved, limits or {"token_budget": 10_000})


def _packager():
    return LLMAgentTaskContextPackager()


# --- required task fields are preserved -------------------------------------------------


def test_required_task_fields_are_preserved():
    task_context = _task_context(inputs={"k": "v"}, constraints=["c1", "c2"])
    budgeted = _budgeted(task_context, [])

    package = _packager().package(task_context, budgeted)

    assert isinstance(package, AgentContextPackage)
    assert package.task["task_id"] == task_context.task_id
    assert package.task["agent_id"] == task_context.agent_id
    assert package.task["scope_id"] == task_context.scope_id
    assert package.task["objective"] == task_context.objective
    assert package.task["inputs"] == {"k": "v"}
    assert package.constraints == ["c1", "c2"]


# --- budgeted context is packaged without reintroducing dropped data ---------------------


def test_dropped_context_is_never_reintroduced():
    # created first (older) so compaction's own newest-first remainder
    # ordering does not prefer it over the survivor created after it
    oversized = _project_context_dict("filler content " * 300)
    survivor = _project_context_dict("short survivor content")
    task_context = _task_context()

    budgeted = _budgeted(task_context, [survivor, oversized], limits={"token_budget": 8})
    assert oversized["context_id"] in {e["context_id"] for e in budgeted.dropped_context}

    package = _packager().package(task_context, budgeted)

    packaged_ids = {msg["metadata"]["context_id"] for msg in package.context}
    assert oversized["context_id"] not in packaged_ids
    assert len(package.context) == len(budgeted.selected_context)


def test_context_messages_use_existing_message_envelope():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    budgeted = _budgeted(task_context, [entry])

    package = _packager().package(task_context, budgeted)

    assert len(package.context) == 1
    message = package.context[0]
    assert message["role"] == CONTEXT_ROLE
    assert message["content"] == "hello world"
    assert message["metadata"]["context_id"] == entry["context_id"]
    assert message["metadata"]["scope_id"] == "scope-1"
    assert message["metadata"]["context_type"] == "fact"


# --- provenance survives packaging --------------------------------------------------------


def test_provenance_survives_packaging_even_for_dropped_entries():
    from backend.llm.context_provenance import LLMContextProvenance

    oversized = _project_context_dict("filler content " * 300)
    provenance = [
        LLMContextProvenance(
            context_id=oversized["context_id"],
            source_type="project_context",
            source_id=oversized["context_id"],
            excerpt="x",
        )
    ]
    task_context = _task_context()
    budgeted = _budgeted(task_context, [oversized], limits={"token_budget": 1}, provenance=provenance)

    package = _packager().package(task_context, budgeted)

    provenance_ids = {p["context_id"] for p in package.provenance}
    assert oversized["context_id"] in provenance_ids
    assert all(isinstance(p, dict) for p in package.provenance)


def test_surviving_context_message_carries_its_own_provenance():
    from backend.llm.context_provenance import LLMContextProvenance

    entry = _project_context_dict("hello world")
    provenance = [
        LLMContextProvenance(
            context_id=entry["context_id"], source_type="project_context", source_id=entry["context_id"], excerpt="x"
        )
    ]
    task_context = _task_context()
    budgeted = _budgeted(task_context, [entry], provenance=provenance)

    package = _packager().package(task_context, budgeted)

    assert package.context[0]["metadata"]["provenance"]["source_id"] == entry["context_id"]


# --- ordering follows repository conventions -----------------------------------------------


def test_context_ordering_matches_selected_context_insertion_order():
    first = _project_context_dict("first entry", context_id="ctx-1")
    second = _project_context_dict("second entry", context_id="ctx-2")
    third = _project_context_dict("third entry", context_id="ctx-3")
    task_context = _task_context()

    budgeted = _budgeted(task_context, [first, second, third])
    package = _packager().package(task_context, budgeted)

    assert [msg["metadata"]["context_id"] for msg in package.context] == ["ctx-1", "ctx-2", "ctx-3"]


# --- empty optional context works -----------------------------------------------------------


def test_empty_selected_context_and_memories_works():
    task_context = _task_context()
    budgeted = _budgeted(task_context, [])

    package = _packager().package(task_context, budgeted)

    assert package.context == []
    assert package.memories == []
    assert package.provenance == []
    assert package.task["objective"] == task_context.objective


def test_request_context_defaults_to_absent():
    task_context = _task_context()
    budgeted = _budgeted(task_context, [])

    package = _packager().package(task_context, budgeted)

    assert "request_context" not in package.metadata


def test_request_context_is_merged_under_its_own_key():
    task_context = _task_context()
    budgeted = _budgeted(task_context, [])

    package = _packager().package(task_context, budgeted, request_context={"request_id": "req-1"})

    assert package.metadata["request_context"] == {"request_id": "req-1"}
    assert package.metadata["task_id"] == task_context.task_id


# --- packaging does not mutate stored context ------------------------------------------------


def test_packaging_is_side_effect_free():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    budgeted = _budgeted(task_context, [entry])

    original_task_context = task_context
    original_selected_context = list(budgeted.selected_context)
    original_provenance = list(budgeted.provenance)

    _packager().package(task_context, budgeted, request_context={"k": "v"})

    assert task_context == original_task_context
    assert budgeted.selected_context == original_selected_context
    assert budgeted.provenance == original_provenance


def test_packaging_is_deterministic():
    entry = _project_context_dict("hello world")
    task_context = _task_context()
    budgeted = _budgeted(task_context, [entry])

    first = _packager().package(task_context, budgeted)
    second = _packager().package(task_context, budgeted)

    assert first == second


# --- invalid input is rejected -----------------------------------------------------------------


def test_invalid_task_context_type_rejected():
    task_context = _task_context()
    budgeted = _budgeted(task_context, [])

    with pytest.raises(InvalidContextPackageError):
        _packager().package("not-a-task-context", budgeted)


def test_invalid_budgeted_context_type_rejected():
    task_context = _task_context()

    with pytest.raises(InvalidContextPackageError):
        _packager().package(task_context, "not-a-budgeted-context")


def test_mismatched_task_and_budgeted_context_rejected():
    task_context_a = _task_context()
    task_context_b = _task_context()
    budgeted_b = _budgeted(task_context_b, [])

    with pytest.raises(InvalidContextPackageError):
        _packager().package(task_context_a, budgeted_b)


def test_invalid_request_context_rejected():
    task_context = _task_context()
    budgeted = _budgeted(task_context, [])

    with pytest.raises(InvalidContextPackageError):
        _packager().package(task_context, budgeted, request_context="not-a-dict")
