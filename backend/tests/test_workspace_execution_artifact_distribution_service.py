import pytest

from backend.session import (
    ARTIFACT_DISTRIBUTION_STATUS_FAILED,
    ARTIFACT_DISTRIBUTION_STATUS_PUBLISHED,
    WorkspaceExecutionArtifactDistribution,
    WorkspaceExecutionArtifactDistributionError as Error,
    WorkspaceExecutionArtifactDistributionService,
)


class _FakeIntegrityService:
    def __init__(self, verified_versions=None):
        self._verified_versions = set(verified_versions or ())

    def verify(self, version_id):
        return version_id in self._verified_versions


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


class _FakeVersion:
    def __init__(self, checksum):
        self.checksum = checksum


class _FakeVersionResolver:
    def __init__(self, versions=None):
        self._versions = dict(versions or {})

    def resolve(self, version_id):
        if version_id not in self._versions:
            raise ValueError(f"unknown version {version_id!r}")

        return self._versions[version_id]


class _FakeChecksumProvider:
    def __init__(self):
        self._checksums = {}

    def checksum(self, version_id, target):
        return self._checksums[(version_id, target)]

    def set_checksum(self, version_id, target, checksum):
        self._checksums[(version_id, target)] = checksum


def _build():
    integrity = _FakeIntegrityService({"version-1"})
    promotions = _FakePromotionService()
    resolver = _FakeVersionResolver({"version-1": _FakeVersion("sha256:one")})
    checksum_provider = _FakeChecksumProvider()
    service = WorkspaceExecutionArtifactDistributionService(integrity, promotions, resolver, checksum_provider)
    return integrity, promotions, resolver, checksum_provider, service


class TestWorkspaceExecutionArtifactDistributionService:
    def test_publish_and_verify(self):
        integrity, promotions, resolver, checksum_provider, service = _build()
        checksum_provider.set_checksum("version-1", "us-east", "sha256:one")

        distribution = service.publish("artifact-1", "version-1", "us-east")

        assert isinstance(distribution, WorkspaceExecutionArtifactDistribution)
        assert distribution.status == ARTIFACT_DISTRIBUTION_STATUS_PUBLISHED
        assert distribution.checksum == "sha256:one"
        assert service.verify(distribution.distribution_id) is True

        with pytest.raises(Error):
            service.publish("artifact-1", "unverified-version", "us-east")

    def test_promotion_requirement(self):
        integrity, promotions, resolver, checksum_provider, service = _build()
        checksum_provider.set_checksum("version-1", "PRODUCTION", "sha256:one")

        with pytest.raises(Error):
            service.publish("artifact-1", "version-1", "PRODUCTION")

        promotions.add("artifact-1", _FakePromotion("version-1", "PRODUCTION", "ACTIVE"))

        distribution = service.publish("artifact-1", "version-1", "PRODUCTION")

        assert distribution.status == ARTIFACT_DISTRIBUTION_STATUS_PUBLISHED

    def test_checksum_mismatch(self):
        integrity, promotions, resolver, checksum_provider, service = _build()
        checksum_provider.set_checksum("version-1", "us-east", "sha256:corrupted")

        distribution = service.publish("artifact-1", "version-1", "us-east")

        assert distribution.status == ARTIFACT_DISTRIBUTION_STATUS_FAILED
        assert distribution.checksum == "sha256:corrupted"
        assert service.verify(distribution.distribution_id) is True

    def test_retry(self):
        integrity, promotions, resolver, checksum_provider, service = _build()
        checksum_provider.set_checksum("version-1", "us-east", "sha256:corrupted")

        first_attempt = service.publish("artifact-1", "version-1", "us-east")
        assert first_attempt.status == ARTIFACT_DISTRIBUTION_STATUS_FAILED

        checksum_provider.set_checksum("version-1", "us-east", "sha256:one")
        second_attempt = service.publish("artifact-1", "version-1", "us-east")

        assert second_attempt.status == ARTIFACT_DISTRIBUTION_STATUS_PUBLISHED
        assert second_attempt.distribution_id != first_attempt.distribution_id
        assert service.targets("version-1") == ("us-east",)

    def test_target_isolation(self):
        integrity, promotions, resolver, checksum_provider, service = _build()
        checksum_provider.set_checksum("version-1", "us-east", "sha256:one")
        checksum_provider.set_checksum("version-1", "eu-west", "sha256:corrupted")

        service.publish("artifact-1", "version-1", "us-east")
        service.publish("artifact-1", "version-1", "eu-west")

        assert service.targets("version-1") == ("us-east",)

    def test_removal(self):
        integrity, promotions, resolver, checksum_provider, service = _build()
        checksum_provider.set_checksum("version-1", "us-east", "sha256:one")

        distribution = service.publish("artifact-1", "version-1", "us-east")
        removed = service.remove(distribution.distribution_id)

        assert removed.status == "REMOVED"
        assert service.targets("version-1") == ()

        with pytest.raises(Error):
            service.remove(distribution.distribution_id)
