import dataclasses

import pytest

from backend.llm import LLMRequest
from backend.llm.context import estimate_text_tokens
from backend.llm.context_compaction import LLMContextCompactionService
from backend.llm.context_injection import CONTEXT_ROLE, LLMContextInjectionService
from backend.llm.context_provenance import LLMContextProvenanceService
from backend.llm.context_retrieval import LLMContextRetrievalService
from backend.llm.context_selection import LLMContextSelectionService
from backend.llm.context_snapshot import LLMContextSnapshotService, UnknownSnapshotError
from backend.llm.project_context import LLMProjectContextService


def _pipeline():
    context_service = LLMProjectContextService()
    retrieval_service = LLMContextRetrievalService(context_service)
    selection_service = LLMContextSelectionService()
    compaction_service = LLMContextCompactionService()
    provenance_service = LLMContextProvenanceService(context_service)
    injection_service = LLMContextInjectionService(
        retrieval_service, selection_service, compaction_service, provenance_service
    )
    snapshot_service = LLMContextSnapshotService()
    return context_service, provenance_service, injection_service, snapshot_service


def test_snapshot_creation():
    context_service, provenance_service, injection_service, snapshot_service = _pipeline()

    context_service.create("notebook-1", "fact", "gradient descent minimizes the loss function")

    prepared = injection_service.prepare("notebook-1", "gradient descent", token_budget=10_000)
    request = LLMRequest(
        model="gpt-4o", messages=[{"role": "user", "content": "explain gradient descent"}]
    )
    injected = injection_service.inject(request, prepared)

    snapshot = snapshot_service.create("req-1", injected)

    assert snapshot.request_id == "req-1"
    assert snapshot.scope_id == "notebook-1"
    assert len(snapshot.context_items) == 1
    assert snapshot.context_items[0]["content"] == "gradient descent minimizes the loss function"
    assert snapshot.snapshot_id is not None
    assert snapshot.created_at is not None

    # only the injected context, never the original user/system messages
    assert not any(item.get("content") == "explain gradient descent" for item in snapshot.context_items)


def test_ordering_preservation():
    context_service, _, injection_service, snapshot_service = _pipeline()

    for i in range(4):
        context_service.create("notebook-1", "fact", f"fact number {i}")

    prepared = injection_service.prepare("notebook-1", "fact", token_budget=10_000)
    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])
    injected = injection_service.inject(request, prepared)

    snapshot = snapshot_service.create("req-2", injected)

    injected_context_contents = [
        m["content"] for m in injected.messages if m["role"] == CONTEXT_ROLE
    ]
    assert [item["content"] for item in snapshot.context_items] == injected_context_contents


def test_provenance_preservation():
    context_service, provenance_service, injection_service, snapshot_service = _pipeline()

    context = context_service.create("notebook-1", "fact", "gradient descent info")
    provenance_service.attach(
        context.context_id,
        {"source_type": "external", "source_id": "paper.pdf#p1", "excerpt": "see paper"},
    )

    prepared = injection_service.prepare("notebook-1", "gradient descent", token_budget=10_000)
    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])
    injected = injection_service.inject(request, prepared)

    snapshot = snapshot_service.create("req-3", injected)

    item = snapshot.context_items[0]
    assert item["provenance"]["source_id"] == "paper.pdf#p1"
    assert item["provenance"]["excerpt"] == "see paper"

    # a context with no attached provenance snapshots as None, not missing
    other = context_service.create("notebook-1", "fact", "gradient descent basics")
    prepared_2 = injection_service.prepare("notebook-1", "gradient descent", token_budget=10_000)
    injected_2 = injection_service.inject(request, prepared_2)
    snapshot_2 = snapshot_service.create("req-3b", injected_2)

    other_item = next(
        i for i in snapshot_2.context_items if i["context_id"] == other.context_id
    )
    assert other_item["provenance"] is None


def test_token_count_consistency():
    context_service, _, injection_service, snapshot_service = _pipeline()

    context_service.create("notebook-1", "fact", "gradient descent minimizes the loss function")

    prepared = injection_service.prepare("notebook-1", "gradient descent", token_budget=10_000)
    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])
    injected = injection_service.inject(request, prepared)

    snapshot = snapshot_service.create("req-4", injected)

    expected = sum(estimate_text_tokens(item["content"]) for item in snapshot.context_items)
    assert snapshot.token_count == expected
    assert snapshot.token_count > 0


def test_request_lookup():
    context_service, _, injection_service, snapshot_service = _pipeline()

    context_service.create("notebook-1", "fact", "some fact")
    prepared = injection_service.prepare("notebook-1", "fact", token_budget=10_000)
    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])
    injected = injection_service.inject(request, prepared)

    first = snapshot_service.create("req-5", injected)
    second = snapshot_service.create("req-5", injected)

    assert snapshot_service.for_request("req-5") == [first, second]
    assert snapshot_service.for_request("unknown-request") == []

    assert snapshot_service.get(first.snapshot_id) == first

    with pytest.raises(UnknownSnapshotError):
        snapshot_service.get("not-a-real-snapshot-id")


def test_immutability():
    context_service, _, injection_service, snapshot_service = _pipeline()

    context_service.create("notebook-1", "fact", "some fact")
    prepared = injection_service.prepare("notebook-1", "fact", token_budget=10_000)
    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])
    injected = injection_service.inject(request, prepared)

    snapshot = snapshot_service.create("req-6", injected)

    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.token_count = 0

    fetched = snapshot_service.get(snapshot.snapshot_id)
    fetched.context_items[0]["content"] = "tampered"

    refetched = snapshot_service.get(snapshot.snapshot_id)
    assert refetched.context_items[0]["content"] == "some fact"


def test_secret_exclusion():
    _, _, _, snapshot_service = _pipeline()

    # simulate an injected request whose context metadata carries a secret,
    # bypassing Commit #1/#6's own upstream checks, to prove this service
    # redacts defensively rather than trusting its input blindly
    leaky_request = LLMRequest(
        model="gpt-4o",
        messages=[
            {
                "role": CONTEXT_ROLE,
                "content": "here is my api_key: sk-abcdefghijklmnopqrstuvwxyz",
                "metadata": {
                    "context_id": "ctx-1",
                    "scope_id": "notebook-1",
                    "context_type": "fact",
                    "provenance": {
                        "source_type": "external",
                        "source_id": "sk-abcdefghijklmnopqrstuvwxyz",
                        "source_version": None,
                        "excerpt": "bearer sometotallyrealtoken12345",
                    },
                },
            }
        ],
    )

    snapshot = snapshot_service.create("req-7", leaky_request)

    item = snapshot.context_items[0]
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in item["content"]
    assert item["content"] == "[REDACTED]"
    assert item["provenance"]["source_id"] == "[REDACTED]"
    assert item["provenance"]["excerpt"] == "[REDACTED]"


def test_creation_does_not_alter_active_request():
    context_service, _, injection_service, snapshot_service = _pipeline()

    context_service.create("notebook-1", "fact", "some fact")
    prepared = injection_service.prepare("notebook-1", "fact", token_budget=10_000)
    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])
    injected = injection_service.inject(request, prepared)

    before_messages = list(injected.messages)

    snapshot_service.create("req-8", injected)

    assert injected.messages == before_messages
