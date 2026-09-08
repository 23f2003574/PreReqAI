import pytest

from backend.agent_capability_registry import (
    ACTIVE,
    ARCHIVED,
    ArchivedCapabilityError,
    DuplicateCapabilityIdError,
    InvalidCapabilityChangesError,
    InvalidCapabilityError,
    JsonCapabilityStore,
    LLMAgentCapability,
    LLMAgentCapabilityRegistry,
    UnknownCapabilityError,
)


def _capability(**overrides):
    fields = {
        "capability_id": "web-search",
        "name": "Web Search",
        "description": "Search the public web for information",
        "category": "retrieval",
        "version": "1.0.0",
    }
    fields.update(overrides)
    return LLMAgentCapability(**fields)


def test_register_and_get():
    registry = LLMAgentCapabilityRegistry()

    registered = registry.register(_capability())

    assert isinstance(registered, LLMAgentCapability)
    assert registered.capability_id == "web-search"
    assert registered.status == ACTIVE
    assert registered.created_at is not None
    assert registered.updated_at is not None

    fetched = registry.get("web-search")
    assert fetched.name == "Web Search"
    assert fetched.category == "retrieval"
    assert fetched.version == "1.0.0"


def test_register_accepts_dict():
    registry = LLMAgentCapabilityRegistry()

    registered = registry.register(
        {
            "capability_id": "code-exec",
            "name": "Code Execution",
            "description": "Run code in a sandbox",
            "category": "code_execution",
            "version": "2.1.0",
        }
    )

    assert registered.capability_id == "code-exec"
    assert registry.get("code-exec").version == "2.1.0"


def test_duplicate_capability_id_rejected():
    registry = LLMAgentCapabilityRegistry()
    registry.register(_capability())

    with pytest.raises(DuplicateCapabilityIdError):
        registry.register(_capability())

    # even an archived capability's id cannot be reused
    registry.archive("web-search")
    with pytest.raises(DuplicateCapabilityIdError):
        registry.register(_capability())


def test_missing_capability():
    registry = LLMAgentCapabilityRegistry()

    with pytest.raises(UnknownCapabilityError):
        registry.get("missing-id")
    with pytest.raises(UnknownCapabilityError):
        registry.update("missing-id", {"name": "new name"})
    with pytest.raises(UnknownCapabilityError):
        registry.archive("missing-id")
    assert registry.exists("missing-id") is False


def test_register_validation():
    registry = LLMAgentCapabilityRegistry()

    with pytest.raises(InvalidCapabilityError):
        registry.register(_capability(capability_id=""))
    with pytest.raises(InvalidCapabilityError):
        registry.register(_capability(name=""))
    with pytest.raises(InvalidCapabilityError):
        registry.register(_capability(description=""))
    with pytest.raises(InvalidCapabilityError):
        registry.register(_capability(category=""))
    with pytest.raises(InvalidCapabilityError):
        registry.register(_capability(version=""))
    with pytest.raises(InvalidCapabilityError):
        registry.register(_capability(metadata="not-a-dict"))
    with pytest.raises(InvalidCapabilityError):
        registry.register("not-a-capability-or-dict")


def test_list_defaults_to_active_only():
    registry = LLMAgentCapabilityRegistry()
    active = registry.register(_capability())
    to_archive = registry.register(_capability(capability_id="code-exec", category="code_execution"))
    registry.archive(to_archive.capability_id)

    assert [c.capability_id for c in registry.list()] == [active.capability_id]
    assert [c.capability_id for c in registry.list(status=ACTIVE)] == [active.capability_id]
    assert [c.capability_id for c in registry.list(status=ARCHIVED)] == [to_archive.capability_id]


def test_list_filters_by_category_and_status():
    registry = LLMAgentCapabilityRegistry()
    registry.register(_capability())
    registry.register(_capability(capability_id="code-exec", category="code_execution"))

    assert [c.capability_id for c in registry.list(category="retrieval")] == ["web-search"]
    assert [c.capability_id for c in registry.list(category="code_execution")] == ["code-exec"]
    assert registry.list(category="nonexistent") == []

    with pytest.raises(InvalidCapabilityError):
        registry.list(status="not-a-status")


def test_update_preserves_identifiers_and_unmentioned_fields():
    registry = LLMAgentCapabilityRegistry()
    registered = registry.register(_capability())

    updated = registry.update("web-search", {"description": "Updated description"})

    assert updated.capability_id == "web-search"
    assert updated.name == registered.name
    assert updated.version == registered.version
    assert updated.description == "Updated description"


def test_update_rejects_immutable_or_unknown_fields():
    registry = LLMAgentCapabilityRegistry()
    registry.register(_capability())

    with pytest.raises(InvalidCapabilityChangesError):
        registry.update("web-search", {"capability_id": "new-id"})
    with pytest.raises(InvalidCapabilityChangesError):
        registry.update("web-search", {"status": ARCHIVED})
    with pytest.raises(InvalidCapabilityChangesError):
        registry.update("web-search", {"created_at": "2020-01-01T00:00:00+00:00"})
    with pytest.raises(InvalidCapabilityChangesError):
        registry.update("web-search", {"nonexistent_field": "x"})
    with pytest.raises(InvalidCapabilityChangesError):
        registry.update("web-search", "not-a-dict")
    with pytest.raises(InvalidCapabilityChangesError):
        registry.update("web-search", {})


def test_update_validates_new_values():
    registry = LLMAgentCapabilityRegistry()
    registry.register(_capability())

    with pytest.raises(InvalidCapabilityError):
        registry.update("web-search", {"name": ""})
    with pytest.raises(InvalidCapabilityError):
        registry.update("web-search", {"category": ""})
    with pytest.raises(InvalidCapabilityError):
        registry.update("web-search", {"version": ""})
    with pytest.raises(InvalidCapabilityError):
        registry.update("web-search", {"metadata": "not-a-dict"})


def test_update_can_change_version_explicitly():
    registry = LLMAgentCapabilityRegistry()
    registry.register(_capability())

    updated = registry.update("web-search", {"version": "1.1.0"})
    assert updated.version == "1.1.0"

    # unrelated updates never silently touch version
    updated_again = registry.update("web-search", {"name": "Web Search v2"})
    assert updated_again.version == "1.1.0"


def test_archived_capability_rejects_update_but_stays_readable():
    registry = LLMAgentCapabilityRegistry()
    registry.register(_capability())
    registry.archive("web-search")

    with pytest.raises(ArchivedCapabilityError):
        registry.update("web-search", {"name": "new name"})

    # archived capabilities remain readable
    assert registry.get("web-search").status == ARCHIVED
    assert registry.exists("web-search") is True

    # archiving is idempotent
    assert registry.archive("web-search").status == ARCHIVED


def test_existing_capabilities_unaffected_by_new_registrations():
    registry = LLMAgentCapabilityRegistry()
    first = registry.register(_capability())
    registry.register(_capability(capability_id="code-exec", category="code_execution"))

    unchanged = registry.get("web-search")
    assert unchanged.name == first.name
    assert unchanged.version == first.version
    assert unchanged.status == first.status


def test_json_store_round_trip(tmp_path):
    path = tmp_path / "capabilities.json"

    registry1 = LLMAgentCapabilityRegistry(store=JsonCapabilityStore(path))
    registry1.register(_capability())
    registry1.register(_capability(capability_id="code-exec", category="code_execution"))
    registry1.archive("code-exec")

    registry2 = LLMAgentCapabilityRegistry(store=JsonCapabilityStore(path))
    assert registry2.get("web-search").status == ACTIVE
    assert registry2.get("code-exec").status == ARCHIVED
    assert [c.capability_id for c in registry2.list()] == ["web-search"]
    assert [c.capability_id for c in registry2.list(status=ARCHIVED)] == ["code-exec"]
