import pytest

from backend.session import (
    ARTIFACT_INTEGRITY_STATUS_CORRUPT,
    ARTIFACT_INTEGRITY_STATUS_VERIFIED,
    WorkspaceExecutionArtifactIntegrity,
    WorkspaceExecutionArtifactIntegrityError as Error,
    WorkspaceExecutionArtifactIntegrityService,
)


class _FakeVersion:
    def __init__(self, artifact_id, version_id, checksum):
        self.artifact_id = artifact_id
        self.version_id = version_id
        self.checksum = checksum


class _FakeVersionResolver:
    def __init__(self, versions=None):
        self._versions = dict(versions or {})

    def resolve(self, version_id):
        if version_id not in self._versions:
            raise ValueError(f"unknown version {version_id!r}")

        return self._versions[version_id]


class _FakeChecksumProvider:
    def __init__(self, checksums=None):
        self._checksums = dict(checksums or {})

    def checksum(self, version_id):
        return self._checksums[version_id]

    def set_checksum(self, version_id, checksum):
        self._checksums[version_id] = checksum


def _build():
    resolver = _FakeVersionResolver(
        {
            "version-1": _FakeVersion("artifact-1", "version-1", "sha256:one"),
            "version-2": _FakeVersion("artifact-1", "version-2", "sha256:two"),
            "version-3": _FakeVersion("artifact-2", "version-3", "sha256:three"),
        }
    )
    provider = _FakeChecksumProvider(
        {
            "version-1": "sha256:one",
            "version-2": "sha256:two",
            "version-3": "sha256:three",
        }
    )
    service = WorkspaceExecutionArtifactIntegrityService(resolver, provider)
    return resolver, provider, service


class TestWorkspaceExecutionArtifactIntegrityService:
    def test_matching_checksum(self):
        _, _, service = _build()

        entry = service.check("version-1")

        assert isinstance(entry, WorkspaceExecutionArtifactIntegrity)
        assert entry.status == ARTIFACT_INTEGRITY_STATUS_VERIFIED
        assert entry.expected_checksum == entry.actual_checksum
        assert service.verify("version-1") is True

    def test_corruption_detection(self):
        _, provider, service = _build()
        provider.set_checksum("version-1", "sha256:tampered")

        entry = service.check("version-1")

        assert entry.status == ARTIFACT_INTEGRITY_STATUS_CORRUPT
        assert entry.expected_checksum == "sha256:one"
        assert entry.actual_checksum == "sha256:tampered"
        assert service.verify("version-1") is False

    def test_version_isolation(self):
        _, provider, service = _build()
        provider.set_checksum("version-1", "sha256:tampered")

        corrupt_entry = service.check("version-1")
        clean_entry = service.check("version-2")

        assert corrupt_entry.status == ARTIFACT_INTEGRITY_STATUS_CORRUPT
        assert clean_entry.status == ARTIFACT_INTEGRITY_STATUS_VERIFIED

    def test_history_ordering(self):
        _, provider, service = _build()

        first = service.check("version-1")
        second = service.check("version-2")
        provider.set_checksum("version-1", "sha256:tampered")
        third = service.check("version-1")

        history = service.history("artifact-1")

        assert history == (first, second, third)
        assert service.history("artifact-2") == ()

    def test_missing_version(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.check("unknown-version")

        with pytest.raises(Error):
            service.verify("unknown-version")

    def test_deterministic_result(self):
        _, _, service = _build()

        first = service.check("version-1")
        second = service.check("version-1")

        assert first.status == second.status == ARTIFACT_INTEGRITY_STATUS_VERIFIED
        assert first.expected_checksum == second.expected_checksum
        assert first.actual_checksum == second.actual_checksum
