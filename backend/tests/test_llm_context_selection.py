import pytest

from backend.llm.context import estimate_text_tokens
from backend.llm.context_selection import LLMContextSelectionService, MixedScopeError
from backend.llm.project_context import LLMProjectContextService


def _service():
    context_service = LLMProjectContextService()
    selection_service = LLMContextSelectionService()
    return context_service, selection_service


def test_relevance_selection():
    context_service, selection_service = _service()

    high = context_service.create(
        "notebook-1", "fact", "gradient descent optimizes the loss function"
    )
    low = context_service.create("notebook-1", "fact", "loss function basics")
    unrelated = context_service.create("notebook-1", "fact", "completely unrelated text")

    selected = selection_service.select(
        [high, low, unrelated], "gradient descent loss function", token_budget=10_000
    )

    ids = [context.context_id for context in selected]
    assert ids.index(high.context_id) < ids.index(low.context_id) < ids.index(unrelated.context_id)
    assert selection_service.score(high, "gradient descent") > selection_service.score(
        unrelated, "gradient descent"
    )


def test_token_budget_enforcement():
    context_service, selection_service = _service()

    small_content = "x" * 4
    big_content = "the quick brown fox jumps over the lazy dog " * 20

    small = context_service.create("notebook-1", "fact", small_content)
    big = context_service.create("notebook-1", "fact", big_content)

    small_tokens = estimate_text_tokens(small_content)
    big_tokens = estimate_text_tokens(big_content)
    assert big_tokens > small_tokens

    # budget fits only the small item, even though big scores identically (0)
    # against an empty task and would otherwise win the recency tie-break
    selected = selection_service.select([small, big], "", token_budget=small_tokens)

    assert [context.context_id for context in selected] == [small.context_id]

    total_tokens = sum(estimate_text_tokens(c.content) for c in selected)
    assert total_tokens <= small_tokens

    # nothing fits at all
    assert selection_service.select([big], "", token_budget=1) == []

    with pytest.raises(ValueError):
        selection_service.select([small], "task", token_budget=0)


def test_version_preference():
    context_service, selection_service = _service()

    original = context_service.create("notebook-1", "fact", "unrelated to the task at hand")
    updated = context_service.update(original.context_id, "still unrelated to the task at hand")

    assert updated.updated_at >= original.updated_at

    # both score 0 against this task -- "otherwise equivalent" -- so the
    # newer copy of the same context_id must be the one kept
    selected = selection_service.select(
        [original, updated], "gradient descent", token_budget=10_000
    )

    assert len(selected) == 1
    assert selected[0].content == "still unrelated to the task at hand"


def test_scope_isolation():
    context_service, selection_service = _service()

    a = context_service.create("notebook-1", "fact", "belongs to notebook-1")
    b = context_service.create("notebook-2", "fact", "belongs to notebook-2")

    with pytest.raises(MixedScopeError):
        selection_service.select([a, b], "task", token_budget=10_000)

    # a single scope is fine
    selected = selection_service.select([a], "task", token_budget=10_000)
    assert [context.context_id for context in selected] == [a.context_id]


def test_deterministic_ordering():
    context_service, selection_service = _service()

    contexts = [
        context_service.create("notebook-1", "fact", f"shared term number {i}") for i in range(4)
    ]

    first_call = selection_service.select(contexts, "shared term", token_budget=10_000)
    second_call = selection_service.select(contexts, "shared term", token_budget=10_000)

    assert [c.context_id for c in first_call] == [c.context_id for c in second_call]


def test_empty_context():
    _, selection_service = _service()

    assert selection_service.select([], "task", token_budget=1000) == []


def test_does_not_mutate_stored_context():
    context_service, selection_service = _service()

    context = context_service.create("notebook-1", "fact", "original content")
    before = context_service.get(context.context_id)

    selection_service.select([context], "original content", token_budget=10_000)

    after = context_service.get(context.context_id)
    assert after.content == before.content
    assert after.updated_at == before.updated_at
