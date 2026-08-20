import pytest

from backend.session import (
    ARTIFACT_DISTRIBUTION_FAILOVER_STATUS_FAILED,
    ARTIFACT_DISTRIBUTION_FAILOVER_STATUS_SUCCEEDED,
    ExecutionArtifactDistributionFailover,
    ExecutionArtifactDistributionFailoverError as Error,
    ExecutionArtifactDistributionFailoverService,
)


class _FakeIntegrityService:
    def __init__(self, verified_versions=None):
        self._verified_versions = set(verified_versions or ())

    def verify(self, version_id):
        return version_id in self._verified_versions


class _FakeDistribution:
    def __init__(self, status):
        self.status = status


class _FakeDistributionService:
    def __init__(self, healthy_targets=None):
        self._healthy_targets = set(healthy_targets or ())
        self.attempts = []

    def publish(self, artifact_id, version_id, target):
        self.attempts.append(target)

        return _FakeDistribution("PUBLISHED" if target in self._healthy_targets else "FAILED")

    def set_healthy(self, target, healthy):
        if healthy:
            self._healthy_targets.add(target)
        else:
            self._healthy_targets.discard(target)


def _build(healthy_targets=None):
    integrity = _FakeIntegrityService({"version-1"})
    distribution = _FakeDistributionService(healthy_targets)
    service = ExecutionArtifactDistributionFailoverService(integrity, distribution)
    return integrity, distribution, service


class TestExecutionArtifactDistributionFailoverService:
    def test_primary_distribution(self):
        integrity, distribution, service = _build(healthy_targets={"us-east"})
        service.register("artifact-1", "version-1", ["us-east", "eu-west"])

        outcome = service.execute("artifact-1", "version-1")

        assert isinstance(outcome, ExecutionArtifactDistributionFailover)
        assert outcome.status == ARTIFACT_DISTRIBUTION_FAILOVER_STATUS_SUCCEEDED
        assert outcome.selected_target == "us-east"
        assert distribution.attempts == ["us-east"]

    def test_backup_failover(self):
        integrity, distribution, service = _build(healthy_targets={"eu-west"})
        service.register("artifact-1", "version-1", ["us-east", "eu-west", "ap-south"])

        outcome = service.execute("artifact-1", "version-1")

        assert outcome.status == ARTIFACT_DISTRIBUTION_FAILOVER_STATUS_SUCCEEDED
        assert outcome.selected_target == "eu-west"
        assert distribution.attempts == ["us-east", "eu-west"]
        assert service.select("artifact-1", "version-1") == "eu-west"

    def test_failed_target_skip(self):
        integrity, distribution, service = _build(healthy_targets={"ap-south"})
        service.register("artifact-1", "version-1", ["us-east", "eu-west", "ap-south"])

        outcome = service.execute("artifact-1", "version-1")

        assert outcome.selected_target == "ap-south"
        assert distribution.attempts == ["us-east", "eu-west", "ap-south"]

    def test_integrity_failure(self):
        integrity, distribution, service = _build(healthy_targets={"us-east"})
        service.register("artifact-1", "unverified-version", ["us-east"])

        with pytest.raises(Error):
            service.execute("artifact-1", "unverified-version")

        assert distribution.attempts == []

    def test_all_target_failure(self):
        integrity, distribution, service = _build(healthy_targets=set())
        service.register("artifact-1", "version-1", ["us-east", "eu-west"])

        outcome = service.execute("artifact-1", "version-1")

        assert outcome.status == ARTIFACT_DISTRIBUTION_FAILOVER_STATUS_FAILED
        assert outcome.selected_target is None
        assert service.status("artifact-1", "version-1") == outcome

    def test_deterministic_selection(self):
        integrity, distribution, service = _build(healthy_targets={"eu-west", "ap-south"})
        service.register("artifact-1", "version-1", ["us-east", "eu-west", "ap-south"])

        first = service.execute("artifact-1", "version-1")
        second = service.execute("artifact-1", "version-1")

        assert first.selected_target == second.selected_target == "eu-west"
        assert distribution.attempts == ["us-east", "eu-west", "us-east", "eu-west"]
