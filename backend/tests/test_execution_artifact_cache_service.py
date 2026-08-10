from datetime import (
    timedelta,
)

import pytest

from backend.session import (
    ExecutionArtifactCacheEntry,
    ExecutionArtifactCacheError as Error,
    ExecutionArtifactCacheService,
)


def _build(ttl=timedelta(minutes=15)):
    return ExecutionArtifactCacheService(ttl=ttl)


class TestExecutionArtifactCacheService:
    def test_cache_and_get(self):
        cache_service = _build()

        entry = cache_service.put("artifact-1", 1, "user-1")

        assert isinstance(entry, ExecutionArtifactCacheEntry)
        assert entry.artifact_id == "artifact-1"
        assert entry.version == 1
        assert entry.consumer == "user-1"

        fetched = cache_service.get("artifact-1", "user-1")

        assert fetched == entry

    def test_cache_miss(self):
        cache_service = _build()

        assert cache_service.get("artifact-1", "user-1") is None

    def test_put_replaces_prior_version(self):
        cache_service = _build()

        cache_service.put("artifact-1", 1, "user-1")
        second = cache_service.put("artifact-1", 2, "user-1")

        fetched = cache_service.get("artifact-1", "user-1")

        assert fetched == second
        assert fetched.version == 2

    def test_expiry(self):
        cache_service = _build(ttl=timedelta(seconds=-1))

        entry = cache_service.put("artifact-1", 1, "user-1")

        assert cache_service.get("artifact-1", "user-1") is None
        assert cache_service.expired() == [entry]

    def test_invalidation(self):
        cache_service = _build()

        cache_service.put("artifact-1", 1, "user-1")
        cache_service.put("artifact-1", 2, "user-2")
        cache_service.put("artifact-2", 1, "user-1")

        removed = cache_service.invalidate("artifact-1")

        assert {entry.consumer for entry in removed} == {"user-1", "user-2"}
        assert cache_service.get("artifact-1", "user-1") is None
        assert cache_service.get("artifact-1", "user-2") is None
        assert cache_service.get("artifact-2", "user-1") is not None

    def test_consumer_isolation(self):
        cache_service = _build()

        first = cache_service.put("artifact-1", 1, "user-1")
        second = cache_service.put("artifact-1", 5, "user-2")

        assert cache_service.get("artifact-1", "user-1") == first
        assert cache_service.get("artifact-1", "user-2") == second
        assert first.version != second.version

    def test_cleanup(self):
        cache_service = _build(ttl=timedelta(seconds=-1))

        entry = cache_service.put("artifact-1", 1, "user-1")

        removed = cache_service.cleanup()

        assert removed == [entry]
        assert cache_service.expired() == []

        remade = cache_service.put("artifact-1", 1, "user-1")
        assert remade.cache_id != entry.cache_id

    def test_rejects_invalid_arguments(self):
        cache_service = _build()

        with pytest.raises(Error):
            cache_service.put("", 1, "user-1")

        with pytest.raises(Error):
            cache_service.get("artifact-1", "")

        with pytest.raises(Error):
            cache_service.invalidate("")
