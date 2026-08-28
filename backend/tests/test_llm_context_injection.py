from backend.llm import LLMRequest
from backend.llm.context_compaction import LLMContextCompactionService
from backend.llm.context_injection import CONTEXT_ROLE, LLMContextInjectionService
from backend.llm.context_provenance import LLMContextProvenanceService
from backend.llm.context_retrieval import LLMContextRetrievalService
from backend.llm.context_selection import LLMContextSelectionService, content_tokens
from backend.llm.project_context import LLMProjectContextService


def _services():
    context_service = LLMProjectContextService()
    retrieval_service = LLMContextRetrievalService(context_service)
    selection_service = LLMContextSelectionService()
    compaction_service = LLMContextCompactionService()
    provenance_service = LLMContextProvenanceService(context_service)
    injection_service = LLMContextInjectionService(
        retrieval_service, selection_service, compaction_service, provenance_service
    )
    return context_service, provenance_service, injection_service


def test_retrieval_selection_injection_pipeline():
    context_service, _, injection_service = _services()

    relevant = context_service.create(
        "notebook-1", "fact", "gradient descent minimizes the loss function"
    )
    context_service.create("notebook-1", "fact", "completely unrelated content")

    prepared = injection_service.prepare("notebook-1", "gradient descent", token_budget=10_000)
    assert [c.context_id for c in prepared][0] == relevant.context_id

    request = LLMRequest(
        model="gpt-4o", messages=[{"role": "user", "content": "explain gradient descent"}]
    )
    injected = injection_service.inject(request, prepared)

    assert injected.messages[-1] == {"role": "user", "content": "explain gradient descent"}
    assert injected.messages[0]["role"] == CONTEXT_ROLE
    assert injected.messages[0]["content"] == "gradient descent minimizes the loss function"
    injected.validate()  # still a well-formed LLMRequest


def test_budget_enforcement():
    context_service, _, injection_service = _services()

    for i in range(5):
        context_service.create("notebook-1", "fact", f"fact number {i} " * 30)

    prepared = injection_service.prepare("notebook-1", "fact", token_budget=10)

    assert sum(content_tokens(c) for c in prepared) <= 10
    assert len(prepared) < 5


def test_provenance_preservation():
    context_service, provenance_service, injection_service = _services()

    context = context_service.create("notebook-1", "fact", "gradient descent info")
    provenance_service.attach(
        context.context_id,
        {"source_type": "external", "source_id": "paper.pdf#p1", "excerpt": "see paper"},
    )

    prepared = injection_service.prepare("notebook-1", "gradient descent", token_budget=10_000)
    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])
    injected = injection_service.inject(request, prepared)

    context_message = next(m for m in injected.messages if m["role"] == CONTEXT_ROLE)
    assert context_message["metadata"]["context_id"] == context.context_id
    assert context_message["metadata"]["provenance"]["source_id"] == "paper.pdf#p1"
    assert context_message["metadata"]["provenance"]["excerpt"] == "see paper"

    # a context with no attached provenance simply carries none
    other = context_service.create("notebook-1", "fact", "gradient descent basics")
    other_message = injection_service._message_for(other)
    assert "provenance" not in other_message["metadata"]


def test_scope_isolation():
    context_service, _, injection_service = _services()

    context_service.create("notebook-1", "fact", "belongs to notebook-1")
    context_service.create("notebook-2", "fact", "belongs to notebook-2")

    prepared = injection_service.prepare("notebook-1", "belongs", token_budget=10_000)

    assert len(prepared) == 1
    assert all(context.scope_id == "notebook-1" for context in prepared)


def test_existing_message_preservation():
    _, _, injection_service = _services()

    original_messages = [
        {"role": "system", "content": "You are a tutor."},
        {"role": "user", "content": "explain backprop"},
    ]
    request = LLMRequest(model="gpt-4o", messages=list(original_messages))

    injected = injection_service.inject(request, [])

    assert injected.messages == original_messages
    assert injected is not request
    assert injected.messages is not request.messages


def test_empty_context():
    context_service, _, injection_service = _services()

    prepared = injection_service.prepare("empty-scope", "anything", token_budget=1000)
    assert prepared == []

    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])
    injected = injection_service.inject(request, prepared)

    assert injected.messages == request.messages


def test_deterministic_injection():
    context_service, _, injection_service = _services()

    for i in range(4):
        context_service.create("notebook-1", "fact", f"shared term number {i}")

    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])

    prepared_1 = injection_service.prepare("notebook-1", "shared term", token_budget=10_000)
    prepared_2 = injection_service.prepare("notebook-1", "shared term", token_budget=10_000)

    injected_1 = injection_service.inject(request, prepared_1)
    injected_2 = injection_service.inject(request, prepared_2)

    assert injected_1.messages == injected_2.messages


def test_injection_does_not_mutate_persisted_context():
    context_service, _, injection_service = _services()

    context = context_service.create("notebook-1", "fact", "original content")
    before = context_service.get(context.context_id)

    prepared = injection_service.prepare("notebook-1", "original", token_budget=10_000)
    request = LLMRequest(model="gpt-4o", messages=[{"role": "user", "content": "q"}])
    injection_service.inject(request, prepared)

    after = context_service.get(context.context_id)
    assert after.content == before.content
    assert after.updated_at == before.updated_at
