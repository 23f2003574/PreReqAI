import pytest

from backend.llm.context_version import (
    LLMContextVersion,
    LLMContextVersionService,
    UnknownContextVersionError,
)
from backend.llm.project_context import LLMProjectContextService, UnknownProjectContextError


def _services():
    context_service = LLMProjectContextService()
    version_service = LLMContextVersionService(context_service)
    return context_service, version_service


def test_first_snapshot():
    context_service, version_service = _services()
    context = context_service.create("notebook-1", "summary", "v1 content")

    version = version_service.snapshot(context.context_id)

    assert isinstance(version, LLMContextVersion)
    assert version.context_id == context.context_id
    assert version.version == 1
    assert version.content == "v1 content"
    assert version.version_id is not None
    assert version.created_at is not None


def test_update_creates_new_version():
    context_service, version_service = _services()
    context = context_service.create("notebook-1", "summary", "v1 content")

    first = version_service.snapshot(context.context_id)

    context_service.update(context.context_id, "v2 content")
    second = version_service.snapshot(context.context_id)

    assert first.version == 1
    assert second.version == 2
    assert second.content == "v2 content"

    # the earlier version's own content is untouched by the later update
    assert version_service.get(context.context_id, 1).content == "v1 content"


def test_latest_lookup():
    context_service, version_service = _services()
    context = context_service.create("notebook-1", "summary", "v1 content")

    version_service.snapshot(context.context_id)
    context_service.update(context.context_id, "v2 content")
    version_service.snapshot(context.context_id)
    context_service.update(context.context_id, "v3 content")
    latest = version_service.snapshot(context.context_id)

    assert version_service.latest(context.context_id) == latest
    assert version_service.latest(context.context_id).version == 3

    other = context_service.create("notebook-1", "fact", "never snapshotted")
    with pytest.raises(UnknownContextVersionError):
        version_service.latest(other.context_id)


def test_history_ordering():
    context_service, version_service = _services()
    context = context_service.create("notebook-1", "summary", "v1 content")

    version_service.snapshot(context.context_id)
    context_service.update(context.context_id, "v2 content")
    version_service.snapshot(context.context_id)
    context_service.update(context.context_id, "v3 content")
    version_service.snapshot(context.context_id)

    history = version_service.history(context.context_id)

    assert [entry.version for entry in history] == [1, 2, 3]
    assert [entry.content for entry in history] == ["v1 content", "v2 content", "v3 content"]


def test_immutable_version():
    context_service, version_service = _services()
    context = context_service.create("notebook-1", "fact", {"count": 1})

    version_service.snapshot(context.context_id)

    # mutating the context's live content afterwards must not retroactively
    # change the already-recorded version
    context_service.update(context.context_id, {"count": 2})

    stored = version_service.get(context.context_id, 1)
    assert stored.content == {"count": 1}

    # mutating a fetched version's content must not affect what is stored
    stored.content["count"] = 999
    refetched = version_service.get(context.context_id, 1)
    assert refetched.content == {"count": 1}

    with pytest.raises(UnknownContextVersionError):
        version_service.get(context.context_id, 42)


def test_context_isolation():
    context_service, version_service = _services()
    context_a = context_service.create("notebook-1", "summary", "belongs to a")
    context_b = context_service.create("notebook-1", "summary", "belongs to b")

    version_service.snapshot(context_a.context_id)
    context_service.update(context_a.context_id, "a updated")
    version_service.snapshot(context_a.context_id)

    version_service.snapshot(context_b.context_id)

    assert len(version_service.history(context_a.context_id)) == 2
    assert len(version_service.history(context_b.context_id)) == 1
    assert version_service.latest(context_b.context_id).content == "belongs to b"


def test_snapshot_of_missing_context_raises():
    _, version_service = _services()

    with pytest.raises(UnknownProjectContextError):
        version_service.snapshot("missing-context")
