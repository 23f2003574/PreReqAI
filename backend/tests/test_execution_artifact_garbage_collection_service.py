import pytest

from backend.session import (
    ARTIFACT_GARBAGE_REASON_RETENTION_EXPIRED,
    ExecutionArtifactGarbageCollectionError as Error,
    ExecutionArtifactGarbageCollectionService,
    ExecutionArtifactGarbageRecord,
)


class _FakeVersion:
    def __init__(self, artifact_id, version_id):
        self.artifact_id = artifact_id
        self.version_id = version_id


class _FakeVersionService:
    def __init__(self, versions_by_artifact=None):
        self._versions_by_artifact = versions_by_artifact if versions_by_artifact is not None else {}

    def history(self, artifact_id):
        return tuple(self._versions_by_artifact.get(artifact_id, ()))

    def add(self, artifact_id, version_id):
        version = _FakeVersion(artifact_id, version_id)
        self._versions_by_artifact.setdefault(artifact_id, []).append(version)
        return version


class _FakeVersionResolver:
    def __init__(self, versions_by_artifact):
        self._versions_by_artifact = versions_by_artifact

    def resolve(self, version_id):
        for versions in self._versions_by_artifact.values():
            for version in versions:
                if version.version_id == version_id:
                    return version

        raise ValueError(f"unknown version {version_id!r}")


class _FakeRetentionService:
    def __init__(self, eligible_versions=None):
        self._eligible_versions = set(eligible_versions or ())

    def eligible(self, version_id):
        return version_id in self._eligible_versions

    def expire(self, version_id):
        self._eligible_versions.discard(version_id)

    def set_eligible(self, version_id):
        self._eligible_versions.add(version_id)


class _FakePromotion:
    def __init__(self, version_id, target_stage, status):
        self.version_id = version_id
        self.target_stage = target_stage
        self.status = status


class _FakePromotionService:
    def __init__(self):
        self._promotions_by_artifact = {}

    def history(self, artifact_id):
        return tuple(self._promotions_by_artifact.get(artifact_id, ()))

    def add(self, artifact_id, promotion):
        self._promotions_by_artifact.setdefault(artifact_id, []).append(promotion)


def _build():
    versions_by_artifact = {}
    version_service = _FakeVersionService(versions_by_artifact)
    resolver = _FakeVersionResolver(versions_by_artifact)
    retention = _FakeRetentionService()
    promotions = _FakePromotionService()
    service = ExecutionArtifactGarbageCollectionService(version_service, resolver, retention, promotions)
    return version_service, retention, promotions, service


class TestExecutionArtifactGarbageCollectionService:
    def test_expired_version_detection(self):
        version_service, retention, promotions, service = _build()
        version_service.add("artifact-1", "version-fresh")
        version_service.add("artifact-1", "version-expired")
        retention.set_eligible("version-fresh")

        candidates = service.scan("artifact-1")

        assert candidates == ("version-expired",)

    def test_production_protection(self):
        version_service, retention, promotions, service = _build()
        version_service.add("artifact-1", "version-prod")
        promotions.add("artifact-1", _FakePromotion("version-prod", "PRODUCTION", "ACTIVE"))

        assert service.protected("version-prod") is True
        assert service.scan("artifact-1") == ()

        with pytest.raises(Error):
            service.mark("version-prod")

    def test_mark_and_collect(self):
        version_service, retention, promotions, service = _build()
        version_service.add("artifact-1", "version-expired")

        record = service.mark("version-expired")

        assert isinstance(record, ExecutionArtifactGarbageRecord)
        assert record.artifact_id == "artifact-1"
        assert record.version_id == "version-expired"
        assert record.reason == ARTIFACT_GARBAGE_REASON_RETENTION_EXPIRED
        assert record.deleted_at is None

        collected = service.collect("artifact-1")

        assert len(collected) == 1
        assert collected[0].version_id == "version-expired"
        assert collected[0].deleted_at is not None

    def test_repeated_collection(self):
        version_service, retention, promotions, service = _build()
        version_service.add("artifact-1", "version-expired")
        service.mark("version-expired")

        first_pass = service.collect("artifact-1")
        second_pass = service.collect("artifact-1")

        assert len(first_pass) == 1
        assert second_pass == ()

        remarked = service.mark("version-expired")
        assert remarked.deleted_at is None
        assert remarked.record_id != first_pass[0].record_id

    def test_retention_enforcement(self):
        version_service, retention, promotions, service = _build()
        version_service.add("artifact-1", "version-active")
        retention.set_eligible("version-active")

        assert service.protected("version-active") is True

        with pytest.raises(Error):
            service.mark("version-active")

    def test_history(self):
        version_service, retention, promotions, service = _build()
        version_service.add("artifact-1", "version-a")
        version_service.add("artifact-1", "version-b")

        first = service.mark("version-a")
        second = service.mark("version-b")

        history = service.history("artifact-1")

        assert history == (first, second)

        collected = service.collect("artifact-1")
        history_after = service.history("artifact-1")

        assert {record.version_id for record in collected} == {"version-a", "version-b"}
        assert [record.version_id for record in history_after] == ["version-a", "version-b"]
        assert all(record.deleted_at is not None for record in history_after)
