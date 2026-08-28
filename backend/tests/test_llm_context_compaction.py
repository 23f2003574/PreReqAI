import pytest

from backend.llm.context_compaction import LLMContextCompactionService
from backend.llm.context_selection import content_tokens
from backend.llm.project_context import LLMProjectContextService


def _services():
    context_service = LLMProjectContextService()
    compaction_service = LLMContextCompactionService()
    return context_service, compaction_service


def test_below_budget_context_is_unchanged():
    context_service, compaction_service = _services()

    a = context_service.create("notebook-1", "fact", "a short fact")
    b = context_service.create("notebook-1", "fact", "another short fact")

    result = compaction_service.compact([a, b], token_budget=10_000)

    assert [c.context_id for c in result] == [a.context_id, b.context_id]
    assert result[0].content == "a short fact"
    assert result[1].content == "another short fact"
    assert result[0].metadata.get("compacted") is not True
    assert result[0] is not a  # a copy, not the same object


def test_compaction_shrinks_content_to_fit():
    context_service, compaction_service = _services()

    big = context_service.create(
        "notebook-1", "fact", "gradient descent minimizes the loss function. " * 40
    )

    full_tokens = content_tokens(big)
    tight_budget = full_tokens // 4

    result = compaction_service.compact([big], token_budget=tight_budget)

    assert len(result) == 1
    entry = result[0]
    assert entry.context_id == big.context_id
    assert entry.content != big.content
    assert len(entry.content) < len(big.content)
    assert entry.metadata.get("compacted") is True
    assert entry.metadata.get("original_estimated_tokens") == full_tokens
    assert compaction_service.estimate(result) <= tight_budget


def test_priority_preservation():
    context_service, compaction_service = _services()

    system_prompt = context_service.create(
        "notebook-1", "system_prompt", "Always answer accurately and cite your sources."
    )
    important_fact = context_service.create(
        "notebook-1", "fact", "The deadline is fixed and must not slip.", metadata={"priority": "high"}
    )
    ordinary_fact = context_service.create(
        "notebook-1", "fact", "The dataset has ten thousand rows in total."
    )

    # only enough room for the two protected entries, in full
    budget = compaction_service.estimate([system_prompt, important_fact])

    result = compaction_service.compact(
        [system_prompt, important_fact, ordinary_fact], token_budget=budget
    )

    result_ids = {entry.context_id for entry in result}
    assert system_prompt.context_id in result_ids
    assert important_fact.context_id in result_ids
    assert ordinary_fact.context_id not in result_ids
    assert compaction_service.estimate(result) <= budget

    # preserve() surfaces the same protected set directly
    preserved = compaction_service.preserve(
        [system_prompt, important_fact, ordinary_fact], [important_fact.context_id]
    )
    assert {entry.context_id for entry in preserved} == {
        system_prompt.context_id,
        important_fact.context_id,
    }


def test_budget_enforcement_never_exceeds():
    context_service, compaction_service = _services()

    contexts = [
        context_service.create("notebook-1", "fact", f"fact number {i} " * 20) for i in range(6)
    ]

    result = compaction_service.compact(contexts, token_budget=5)

    assert compaction_service.estimate(result) <= 5
    # tiny budget: not everything can survive, whole or compacted
    assert len(result) < len(contexts)


def test_empty_context():
    _, compaction_service = _services()

    assert compaction_service.compact([], token_budget=1000) == []
    assert compaction_service.estimate([]) == 0


def test_deterministic_output():
    context_service, compaction_service = _services()

    contexts = [
        context_service.create("notebook-1", "fact", f"shared content block {i} " * 10)
        for i in range(5)
    ]

    first = compaction_service.compact(contexts, token_budget=30)
    second = compaction_service.compact(contexts, token_budget=30)

    assert [c.context_id for c in first] == [c.context_id for c in second]
    assert [c.content for c in first] == [c.content for c in second]


def test_source_immutability():
    context_service, compaction_service = _services()

    context = context_service.create(
        "notebook-1", "fact", "gradient descent minimizes the loss function. " * 40
    )
    before = context_service.get(context.context_id)

    compaction_service.compact([context], token_budget=5)

    after = context_service.get(context.context_id)
    assert after.content == before.content
    assert after.metadata == before.metadata
    assert context.content == before.content
    assert "compacted" not in context.metadata
