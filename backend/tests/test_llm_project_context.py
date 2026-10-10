import pytest

from backend.llm.project_context import (
    InvalidContentError,
    InvalidContextTypeError,
    JsonLLMProjectContextStore,
    LLMProjectContext,
    LLMProjectContextService,
    SecretContentError,
    UnknownProjectContextError,
)


def test_create_get_update_delete():
    service = LLMProjectContextService()

    context = service.create(
        "notebook-1", "summary", "The dataset has 10k rows.", metadata={"author": "abc"}
    )

    assert isinstance(context, LLMProjectContext)
    assert context.scope_id == "notebook-1"
    assert context.context_type == "summary"
    assert context.content == "The dataset has 10k rows."
    assert context.metadata == {"author": "abc"}
    assert context.context_id is not None
    assert context.created_at is not None
    assert context.updated_at is not None

    fetched = service.get(context.context_id)
    assert fetched.content == "The dataset has 10k rows."

    updated = service.update(context.context_id, "The dataset has 12k rows.")
    assert updated.content == "The dataset has 12k rows."
    assert service.get(context.context_id).content == "The dataset has 12k rows."

    assert service.delete(context.context_id) is True
    assert service.delete(context.context_id) is False

    with pytest.raises(UnknownProjectContextError):
        service.get(context.context_id)


def test_scope_isolation():
    service = LLMProjectContextService()

    service.create("notebook-1", "fact", "belongs to notebook-1")
    service.create("notebook-2", "fact", "belongs to notebook-2")

    notebook_1_items = service.list("notebook-1")
    notebook_2_items = service.list("notebook-2")

    assert [item.content for item in notebook_1_items] == ["belongs to notebook-1"]
    assert [item.content for item in notebook_2_items] == ["belongs to notebook-2"]

    # filtering by type further narrows within a scope
    service.create("notebook-1", "preference", "prefers concise answers")
    facts_only = service.list("notebook-1", "fact")
    assert [item.content for item in facts_only] == ["belongs to notebook-1"]


def test_type_validation():
    service = LLMProjectContextService()

    with pytest.raises(InvalidContextTypeError):
        service.create("notebook-1", "not-a-real-type", "some content")

    with pytest.raises(InvalidContextTypeError):
        service.list("notebook-1", "not-a-real-type")


def test_metadata_preservation():
    service = LLMProjectContextService()

    metadata = {"source": "api", "tags": ["math", "prereq"]}
    context = service.create("api-1", "instruction", "Always show derivations.", metadata=metadata)

    # mutating the caller's dict afterwards must not affect the stored copy
    metadata["tags"].append("mutated")

    fetched = service.get(context.context_id)
    assert fetched.metadata == {"source": "api", "tags": ["math", "prereq"]}

    # content-only update leaves metadata untouched
    updated = service.update(context.context_id, "Always show derivations, briefly.")
    assert updated.metadata == {"source": "api", "tags": ["math", "prereq"]}


def test_missing_context():
    service = LLMProjectContextService()

    with pytest.raises(UnknownProjectContextError):
        service.get("missing-id")

    with pytest.raises(UnknownProjectContextError):
        service.update("missing-id", "new content")

    assert service.delete("missing-id") is False


def test_content_validation():
    service = LLMProjectContextService()

    with pytest.raises(InvalidContentError):
        service.create("notebook-1", "fact", "")

    with pytest.raises(InvalidContentError):
        service.create("notebook-1", "fact", None)

    with pytest.raises(InvalidContentError):
        service.create("notebook-1", "fact", {"nested": object()})


def test_secret_rejection():
    service = LLMProjectContextService()

    with pytest.raises(SecretContentError):
        service.create("notebook-1", "fact", "here is my api_key: sk-abcdefghijklmnop")

    with pytest.raises(SecretContentError):
        service.create(
            "notebook-1", "fact", {"config": {"credential": "sk-abcdefghijklmnopqrstuvwxyz"}}
        )

    context = service.create("notebook-1", "fact", "a perfectly safe fact")
    with pytest.raises(SecretContentError):
        service.update(context.context_id, "Bearer sometotallyrealtoken12345")


def test_json_store_round_trip(tmp_path):
    store = JsonLLMProjectContextStore(tmp_path / "project_context.json")
    service = LLMProjectContextService(store)

    created = service.create("project-1", "system_prompt", "Be concise.", metadata={"v": 1})

    reloaded_service = LLMProjectContextService(
        JsonLLMProjectContextStore(tmp_path / "project_context.json")
    )
    fetched = reloaded_service.get(created.context_id)

    assert fetched.content == "Be concise."
    assert fetched.scope_id == "project-1"
    assert fetched.metadata == {"v": 1}
