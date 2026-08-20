from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionArtifactRegistryService,
    WorkspaceExecutionArtifactRetentionError as Error,
    WorkspaceExecutionArtifactRetentionPolicy,
    WorkspaceExecutionArtifactRetentionService,
)


class _FakeStateRecord:
    def __init__(self, state):
        self.state = state


class _FakeRuntimeStateService:
    def __init__(self, known_runtimes=None):
        self._known_runtimes = set(known_runtimes or ())

    def state(self, runtime_id):
        if runtime_id not in self._known_runtimes:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return _FakeStateRecord("RUNNING")


class _FakeVersion:
    def __init__(self, artifact_id, created_at):
        self.artifact_id = artifact_id
        self.created_at = created_at


class _FakeVersionResolver:
    def __init__(self, versions=None):
        self._versions = dict(versions or {})

    def resolve(self, version_id):
        if version_id not in self._versions:
            raise ValueError(f"unknown version {version_id!r}")

        return self._versions[version_id]


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
    runtime_state_service = _FakeRuntimeStateService({"runtime-1"})
    registry = ExecutionArtifactRegistryService(runtime_state_service)
    resolver = _FakeVersionResolver()
    promotions = _FakePromotionService()
    service = WorkspaceExecutionArtifactRetentionService(registry, resolver, promotions)
    return registry, resolver, promotions, service


class TestWorkspaceExecutionArtifactRetentionService:
    def test_configure_policy(self):
        registry, resolver, promotions, service = _build()
        artifact = registry.register("runtime-1", "model.bin", "MODEL", "/artifacts/model.bin")

        policy = service.configure(artifact.artifact_id, 3600)

        assert isinstance(policy, WorkspaceExecutionArtifactRetentionPolicy)
        assert policy.artifact_id == artifact.artifact_id
        assert policy.retention_seconds == 3600
        assert policy.enabled is True
        assert service.policy(artifact.artifact_id) == policy

    def test_retention_eligibility(self):
        registry, resolver, promotions, service = _build()
        artifact = registry.register("runtime-1", "dataset", "DATASET", "/artifacts/dataset")
        service.configure(artifact.artifact_id, 3600)

        resolver._versions["version-fresh"] = _FakeVersion(
            artifact.artifact_id, datetime.now(timezone.utc)
        )

        assert service.eligible("version-fresh") is True

    def test_production_protection(self):
        registry, resolver, promotions, service = _build()
        artifact = registry.register("runtime-1", "model", "MODEL", "/artifacts/model")
        service.configure(artifact.artifact_id, 60)

        resolver._versions["version-old"] = _FakeVersion(
            artifact.artifact_id, datetime.now(timezone.utc) - timedelta(hours=1)
        )
        promotions.add(artifact.artifact_id, _FakePromotion("version-old", "PRODUCTION", "ACTIVE"))

        assert service.eligible("version-old") is True

    def test_expiry(self):
        registry, resolver, promotions, service = _build()
        artifact = registry.register("runtime-1", "report", "FILE", "/artifacts/report.txt")
        service.configure(artifact.artifact_id, 60)

        resolver._versions["version-old"] = _FakeVersion(
            artifact.artifact_id, datetime.now(timezone.utc) - timedelta(hours=1)
        )

        assert service.eligible("version-old") is False

    def test_disabled_policy(self):
        registry, resolver, promotions, service = _build()
        artifact = registry.register("runtime-1", "dataset", "DATASET", "/artifacts/dataset")
        policy = service.configure(artifact.artifact_id, 60)

        resolver._versions["version-old"] = _FakeVersion(
            artifact.artifact_id, datetime.now(timezone.utc) - timedelta(hours=1)
        )

        assert service.eligible("version-old") is False

        disabled = service.disable(policy.policy_id)

        assert disabled.enabled is False
        assert service.eligible("version-old") is True

    def test_invalid_retention(self):
        registry, resolver, promotions, service = _build()
        artifact = registry.register("runtime-1", "model", "MODEL", "/artifacts/model")

        with pytest.raises(Error):
            service.configure(artifact.artifact_id, 0)

        with pytest.raises(Error):
            service.configure(artifact.artifact_id, -10)

        with pytest.raises(Error):
            service.configure(artifact.artifact_id, None)
