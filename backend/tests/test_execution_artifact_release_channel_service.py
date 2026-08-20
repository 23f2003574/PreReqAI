import pytest

from backend.session import (
    ExecutionArtifactReleaseChannel,
    ExecutionArtifactReleaseChannelError as Error,
    ExecutionArtifactReleaseChannelService,
)


class _FakeIntegrityService:
    def __init__(self, verified_versions=None):
        self._verified_versions = set(verified_versions or ())

    def verify(self, version_id):
        return version_id in self._verified_versions


def _build(verified_versions=None):
    integrity = _FakeIntegrityService(verified_versions or {"version-1", "version-2"})
    service = ExecutionArtifactReleaseChannelService(integrity)
    return integrity, service


class TestExecutionArtifactReleaseChannelService:
    def test_release_version(self):
        integrity, service = _build()

        entry = service.release("artifact-1", "version-1", "CANARY")

        assert isinstance(entry, ExecutionArtifactReleaseChannel)
        assert entry.artifact_id == "artifact-1"
        assert entry.version_id == "version-1"
        assert entry.channel == "CANARY"
        assert entry.status == "ACTIVE"

    def test_current_lookup(self):
        integrity, service = _build()
        service.release("artifact-1", "version-1", "CANARY")
        second = service.release("artifact-1", "version-2", "CANARY")

        current = service.current("artifact-1", "CANARY")

        assert current == second
        assert current.version_id == "version-2"

        with pytest.raises(Error):
            service.current("artifact-1", "STABLE")

    def test_channel_isolation(self):
        integrity, service = _build()
        service.release("artifact-1", "version-1", "CANARY")
        service.release("artifact-1", "version-2", "STABLE")

        assert service.current("artifact-1", "CANARY").version_id == "version-1"
        assert service.current("artifact-1", "STABLE").version_id == "version-2"

    def test_forward_promotion(self):
        integrity, service = _build()
        canary_entry = service.release("artifact-1", "version-1", "CANARY")

        stable_entry = service.promote(canary_entry.channel_id, "STABLE")

        assert stable_entry.channel == "STABLE"
        assert stable_entry.version_id == "version-1"
        assert service.current("artifact-1", "STABLE").version_id == "version-1"

        with pytest.raises(Error):
            service.promote(stable_entry.channel_id, "CANARY")

        with pytest.raises(Error):
            service.promote(stable_entry.channel_id, "STABLE")

    def test_rollback(self):
        integrity, service = _build()
        first = service.release("artifact-1", "version-1", "CANARY")
        second = service.release("artifact-1", "version-2", "CANARY")

        restored = service.rollback(second.channel_id)

        assert restored.version_id == "version-1"
        assert restored.status == "ACTIVE"
        assert service.current("artifact-1", "CANARY").version_id == "version-1"

        history = service.history("artifact-1", "CANARY")
        assert [entry.status for entry in history] == ["SUPERSEDED", "ROLLED_BACK", "ACTIVE"]

        with pytest.raises(Error):
            service.rollback(first.channel_id)

    def test_unverified_version_rejection(self):
        integrity, service = _build()

        with pytest.raises(Error):
            service.release("artifact-1", "unverified-version", "CANARY")
