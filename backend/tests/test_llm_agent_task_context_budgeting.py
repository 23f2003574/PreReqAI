from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_context_budgeting import (
    BudgetedAgentTaskContext,
    InvalidTaskContextBudgetError,
    LLMAgentTaskContextBudgeter,
)
from backend.agent_task_context_resolution import ResolvedAgentTaskContext
from backend.llm.context_compaction import LLMContextCompactionService
from backend.llm.project_context import LLMProjectContextService


def _task_context(relevant_context=None, inputs=None, constraints=None):
    service = LLMAgentTaskContextService()
    return service.create(
        agent_id="agent-1",
        scope_id="scope-1",
        objective="analyze the notebook",
        constraints=constraints or ["read-only"],
        inputs=inputs or {"notebook_id": "nb-1"},
        relevant_context=relevant_context or [],
    )


def _resolved(task_context, selected_context, provenance=None):
    return ResolvedAgentTaskContext(
        task_id=task_context.task_id,
        agent_id=task_context.agent_id,
        scope_id=task_context.scope_id,
        task_context=task_context,
        selected_context=selected_context,
        selected_memories=[],
        excluded_context=[],
        provenance=provenance if provenance is not None else list(task_context.provenance),
        resolution_reasons={},
    )


def _project_context_dict(content, context_type="fact", updated_at=None, context_id=None, metadata=None):
    service = LLMProjectContextService()
    context = service.create("scope-1", context_type, content, metadata=metadata)
    if context_id is not None:
        context.context_id = context_id
    if updated_at is not None:
        context.updated_at = updated_at
    return context.to_dict()


def _budgeter():
    return LLMAgentTaskContextBudgeter()


# --- context already within budget is unchanged ---------------------------------------


def test_context_within_budget_is_unchanged():
    task_context = _task_context()
    entry = _project_context_dict("short content")
    resolved = _resolved(task_context, [entry])

    result = _budgeter().budget(resolved, {"token_budget": 10_000})

    assert isinstance(result, BudgetedAgentTaskContext)
    assert result.selected_context == [entry]
    assert result.dropped_context == []
    assert result.truncation_applied is False


def test_bare_int_limits_accepted():
    task_context = _task_context()
    entry = _project_context_dict("short content")
    resolved = _resolved(task_context, [entry])

    result = _budgeter().budget(resolved, 10_000)

    assert result.budget == 10_000
    assert result.selected_context == [entry]


# --- oversized context is reduced correctly ---------------------------------------------


def test_oversized_context_is_shrunk_not_dropped_when_it_fits_a_preview():
    task_context = _task_context()
    entry = _project_context_dict("long filler text " * 250)
    resolved = _resolved(task_context, [entry])

    result = _budgeter().budget(resolved, {"token_budget": 100})

    assert len(result.selected_context) == 1
    assert result.dropped_context == []
    assert result.truncation_applied is True
    assert result.selected_context[0]["metadata"]["compacted"] is True
    assert result.estimated_tokens <= 100


def test_oversized_context_is_dropped_when_nothing_fits():
    task_context = _task_context()
    entry = _project_context_dict("other filler text " * 250)
    resolved = _resolved(task_context, [entry])

    result = _budgeter().budget(resolved, {"token_budget": 1})

    assert result.selected_context == []
    assert len(result.dropped_context) == 1
    assert result.dropped_context[0]["context_id"] == entry["context_id"]
    assert result.truncation_applied is True
    assert "dropped" in result.reasons[entry["context_id"]]


# --- mandatory inputs survive budgeting --------------------------------------------------


def test_mandatory_task_inputs_and_constraints_survive_budgeting():
    task_context = _task_context(inputs={"k": "v"}, constraints=["c1"])
    entry = _project_context_dict("long filler text " * 250)
    resolved = _resolved(task_context, [entry])

    result = _budgeter().budget(resolved, {"token_budget": 1})

    assert result.task_context.inputs == {"k": "v"}
    assert result.task_context.constraints == ["c1"]


def test_explicit_relevant_context_is_prioritized_over_additional_context():
    explicit_entry = _project_context_dict("mandatory explicit fact", context_id="explicit-1")
    task_context = _task_context(relevant_context=[explicit_entry])

    additional_entry = _project_context_dict("other filler text " * 250, context_id="additional-1")

    resolved = _resolved(task_context, [explicit_entry, additional_entry])

    # a budget that can fit the small mandatory entry but leaves no room
    # for even a compacted preview of the large additional one
    result = _budgeter().budget(resolved, {"token_budget": 8})

    selected_ids = {entry["context_id"] for entry in result.selected_context}
    assert "explicit-1" in selected_ids
    assert "additional-1" not in selected_ids


# --- relevance ordering is respected (compaction's own recency signal) -------------------


def test_more_recent_context_survives_over_older_when_budget_is_tight():
    now = datetime.now(timezone.utc)
    older = _project_context_dict("older fact " + "a" * 200, context_id="older-1", updated_at=now - timedelta(hours=2))
    newer = _project_context_dict("newer fact " + "a" * 200, context_id="newer-1", updated_at=now)

    task_context = _task_context()
    resolved = _resolved(task_context, [older, newer])

    result = _budgeter().budget(resolved, {"token_budget": 54})

    selected_ids = {entry["context_id"] for entry in result.selected_context}
    dropped_ids = {entry["context_id"] for entry in result.dropped_context}
    assert "newer-1" in selected_ids
    assert "older-1" in dropped_ids


# --- compaction is reused when available --------------------------------------------------


class _SpyCompactionService(LLMContextCompactionService):
    def __init__(self):
        super().__init__()
        self.compact_calls = 0

    def compact(self, context, token_budget):
        self.compact_calls += 1
        return super().compact(context, token_budget)


def test_compaction_service_is_actually_invoked():
    task_context = _task_context()
    entry = _project_context_dict("long filler text " * 250)
    resolved = _resolved(task_context, [entry])

    spy = _SpyCompactionService()
    budgeter = LLMAgentTaskContextBudgeter(context_compaction=spy)
    budgeter.budget(resolved, {"token_budget": 100})

    assert spy.compact_calls == 1


# --- provenance survives reduction ----------------------------------------------------------


def test_provenance_survives_even_for_dropped_context():
    from backend.llm.context_provenance import LLMContextProvenance

    entry = _project_context_dict("other filler text " * 250)
    provenance = [
        LLMContextProvenance(
            context_id=entry["context_id"], source_type="project_context", source_id=entry["context_id"], excerpt="x"
        )
    ]
    task_context = _task_context()
    resolved = _resolved(task_context, [entry], provenance=provenance)

    result = _budgeter().budget(resolved, {"token_budget": 1})

    assert entry["context_id"] not in {e["context_id"] for e in result.selected_context}
    assert any(p.context_id == entry["context_id"] for p in result.provenance)


# --- exact budget boundary works -------------------------------------------------------------


def test_exact_budget_boundary_keeps_content_unchanged():
    entry = _project_context_dict("0123456789")  # 10 chars -> estimate_text_tokens = max(1,(10+3)//4) = 3
    task_context = _task_context()
    resolved = _resolved(task_context, [entry])

    result = _budgeter().budget(resolved, {"token_budget": 3})

    assert result.selected_context == [entry]
    assert result.dropped_context == []
    assert result.truncation_applied is False
    assert result.estimated_tokens == 3


def test_one_below_exact_boundary_triggers_truncation():
    entry = _project_context_dict("0123456789")  # estimate = 3
    task_context = _task_context()
    resolved = _resolved(task_context, [entry])

    result = _budgeter().budget(resolved, {"token_budget": 2})

    assert result.truncation_applied is True


# --- budgeting is side-effect free ------------------------------------------------------------


def test_budgeting_is_side_effect_free():
    task_context = _task_context()
    entry = _project_context_dict("some content")
    resolved = _resolved(task_context, [entry])
    original_selected_context = list(resolved.selected_context)
    original_task_context = task_context

    _budgeter().budget(resolved, {"token_budget": 10_000})

    assert resolved.selected_context == original_selected_context
    assert resolved.task_context == original_task_context


# --- invalid input is rejected -----------------------------------------------------------------


def test_invalid_context_type_rejected():
    with pytest.raises(InvalidTaskContextBudgetError):
        _budgeter().budget("not-a-resolved-context", {"token_budget": 100})


def test_invalid_limits_rejected():
    task_context = _task_context()
    resolved = _resolved(task_context, [])

    with pytest.raises(InvalidTaskContextBudgetError):
        _budgeter().budget(resolved, "not-valid-limits")
    with pytest.raises(InvalidTaskContextBudgetError):
        _budgeter().budget(resolved, {"token_budget": 0})
    with pytest.raises(InvalidTaskContextBudgetError):
        _budgeter().budget(resolved, {"token_budget": -1})
    with pytest.raises(InvalidTaskContextBudgetError):
        _budgeter().budget(resolved, {})


def test_entry_missing_context_id_rejected():
    task_context = _task_context()
    resolved = _resolved(task_context, [{"content": "no id here"}])

    with pytest.raises(InvalidTaskContextBudgetError):
        _budgeter().budget(resolved, {"token_budget": 100})
