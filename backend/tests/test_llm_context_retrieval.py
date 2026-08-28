import pytest

from backend.llm.context_retrieval import LLMContextMatch, LLMContextRetrievalService
from backend.llm.project_context import LLMProjectContextService


def _services():
    context_service = LLMProjectContextService()
    retrieval_service = LLMContextRetrievalService(context_service)
    return context_service, retrieval_service


def test_relevant_retrieval():
    context_service, retrieval_service = _services()

    matching = context_service.create(
        "notebook-1", "fact", "Gradient descent minimizes a loss function."
    )
    context_service.create("notebook-1", "fact", "The dataset has 10,000 rows.")

    results = retrieval_service.retrieve("notebook-1", "gradient descent", limit=5)

    assert results[0].context_id == matching.context_id


def test_scope_isolation():
    context_service, retrieval_service = _services()

    context_service.create("notebook-1", "fact", "gradient descent basics")
    other = context_service.create("notebook-2", "fact", "gradient descent basics")

    results = retrieval_service.retrieve("notebook-2", "gradient descent", limit=5)

    assert [item.context_id for item in results] == [other.context_id]

    # scope-1 query must never surface scope-2 content, matching or not
    results = retrieval_service.retrieve("notebook-1", "gradient descent", limit=5)
    assert all(item.scope_id == "notebook-1" for item in results)


def test_ranking():
    context_service, retrieval_service = _services()

    low = context_service.create("notebook-1", "fact", "loss function basics")
    high = context_service.create(
        "notebook-1", "fact", "gradient descent optimizes the loss function"
    )
    none = context_service.create("notebook-1", "fact", "completely unrelated text")

    matches = retrieval_service.rank("notebook-1", "gradient descent loss function")

    ids = [match.context.context_id for match in matches]
    assert ids.index(high.context_id) < ids.index(low.context_id) < ids.index(none.context_id)
    assert matches[0].score > matches[-1].score
    assert all(isinstance(match, LLMContextMatch) for match in matches)


def test_limit_enforcement():
    context_service, retrieval_service = _services()

    for i in range(5):
        context_service.create("notebook-1", "fact", f"fact number {i}")

    results = retrieval_service.retrieve("notebook-1", "fact", limit=2)
    assert len(results) == 2

    with pytest.raises(ValueError):
        retrieval_service.retrieve("notebook-1", "fact", limit=0)

    with pytest.raises(ValueError):
        retrieval_service.retrieve("notebook-1", "fact", limit=-1)


def test_empty_query():
    context_service, retrieval_service = _services()

    older = context_service.create("notebook-1", "fact", "first fact")
    newer = context_service.create("notebook-1", "fact", "second fact")

    results = retrieval_service.retrieve("notebook-1", "", limit=5)

    assert len(results) == 2
    assert all(match.score == 0.0 for match in retrieval_service.rank("notebook-1", ""))
    # falls back to recency: most recently updated first
    assert results[0].context_id == newer.context_id
    assert results[1].context_id == older.context_id


def test_empty_result():
    _, retrieval_service = _services()

    assert retrieval_service.retrieve("empty-scope", "anything", limit=5) == []
    assert retrieval_service.rank("empty-scope", "anything") == []


def test_deterministic_ordering():
    context_service, retrieval_service = _services()

    for i in range(4):
        context_service.create("notebook-1", "fact", f"shared term number {i}")

    first_call = retrieval_service.retrieve("notebook-1", "shared term", limit=4)
    second_call = retrieval_service.retrieve("notebook-1", "shared term", limit=4)

    assert [c.context_id for c in first_call] == [c.context_id for c in second_call]
