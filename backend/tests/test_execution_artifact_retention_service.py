from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionArtifactRetentionError as Error,
    ExecutionArtifactRetentionPolicy,
    ExecutionArtifactRetentionResult,
    ExecutionArtifactRetentionService,
    ExecutionArtifactVersion,
)


class _FakeVersionService:
    """
    Minimal stand-in for an execution artifact version service,
    satisfying the duck-typed `history(artifact_id)` /
    `latest(artifact_id)` contract the retention service depends on,
    with full control over each version's created_at for
    deterministic age-based tests.
    """

    def __init__(self, versions):
        self._versions = list(versions)

    def history(self, artifact_id):
        return [version for version in self._versions if version.artifact_id == artifact_id]

    def latest(self, artifact_id):
        return max(self.history(artifact_id), key=lambda version: version.version)


def _version(artifact_id, version, age_seconds):
    return ExecutionArtifactVersion(
        artifact_id=artifact_id,
        version=version,
        location=f"/tmp/{artifact_id}-v{version}.log",
        created_at=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
    )


class TestExecutionArtifactRetentionService:
    def test_retention_by_age(self):
        version_service = _FakeVersionService(
            [
                _version("artifact-1", 1, age_seconds=100),
                _version("artifact-1", 2, age_seconds=10),
            ]
        )
        retention_service = ExecutionArtifactRetentionService(version_service)
        retention_service.configure(
            "artifact-1", ExecutionArtifactRetentionPolicy(policy_id="policy-1", max_age_seconds=50)
        )

        result = retention_service.apply("artifact-1")

        assert isinstance(result, ExecutionArtifactRetentionResult)
        assert [version.version for version in result.removed] == [1]
        assert [version.version for version in result.retained] == [2]

    def test_retention_by_count(self):
        version_service = _FakeVersionService(
            [_version("artifact-1", number, age_seconds=5 - number) for number in range(1, 6)]
        )
        retention_service = ExecutionArtifactRetentionService(version_service)
        retention_service.configure(
            "artifact-1", ExecutionArtifactRetentionPolicy(policy_id="policy-1", max_versions=2)
        )

        result = retention_service.apply("artifact-1")

        assert [version.version for version in result.removed] == [1, 2, 3]
        assert [version.version for version in result.retained] == [4, 5]

    def test_latest_version_preserved(self):
        version_service = _FakeVersionService(
            [
                _version("artifact-1", 1, age_seconds=1000),
                _version("artifact-1", 2, age_seconds=999),
            ]
        )
        retention_service = ExecutionArtifactRetentionService(version_service)
        retention_service.configure(
            "artifact-1", ExecutionArtifactRetentionPolicy(policy_id="policy-1", max_age_seconds=10)
        )

        result = retention_service.apply("artifact-1")

        assert [version.version for version in result.removed] == [1]
        assert [version.version for version in result.retained] == [2]

    def test_preview_is_read_only(self):
        version_service = _FakeVersionService(
            [
                _version("artifact-1", 1, age_seconds=100),
                _version("artifact-1", 2, age_seconds=10),
            ]
        )
        retention_service = ExecutionArtifactRetentionService(version_service)
        retention_service.configure(
            "artifact-1", ExecutionArtifactRetentionPolicy(policy_id="policy-1", max_age_seconds=50)
        )

        first_preview = retention_service.preview("artifact-1")
        second_preview = retention_service.preview("artifact-1")

        assert first_preview == second_preview
        assert [version.version for version in first_preview.removed] == [1]

        applied = retention_service.apply("artifact-1")
        assert [version.version for version in applied.removed] == [1]

        after_apply = retention_service.preview("artifact-1")
        assert after_apply.removed == ()

    def test_invalid_policy_rejection(self):
        with pytest.raises(Error):
            ExecutionArtifactRetentionPolicy(policy_id="policy-1")

        with pytest.raises(Error):
            ExecutionArtifactRetentionPolicy(policy_id="policy-1", max_versions=0)

        with pytest.raises(Error):
            ExecutionArtifactRetentionPolicy(policy_id="policy-1", max_age_seconds=-5)
