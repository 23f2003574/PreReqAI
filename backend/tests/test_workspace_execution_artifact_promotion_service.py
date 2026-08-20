import pytest

from backend.session import (
    ExecutionArtifactRegistryService,
    WorkspaceExecutionArtifactPromotion,
    WorkspaceExecutionArtifactPromotionError as Error,
    WorkspaceExecutionArtifactPromotionService,
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


class _FakeIntegrityService:
    def __init__(self, verified_versions=None):
        self._verified_versions = set(verified_versions or ())

    def verify(self, version_id):
        return version_id in self._verified_versions

    def set_verified(self, version_id, verified):
        if verified:
            self._verified_versions.add(version_id)
        else:
            self._verified_versions.discard(version_id)


def _build():
    runtime_state_service = _FakeRuntimeStateService({"runtime-1"})
    registry = ExecutionArtifactRegistryService(runtime_state_service)
    integrity = _FakeIntegrityService({"version-1"})
    service = WorkspaceExecutionArtifactPromotionService(registry, integrity)
    return registry, integrity, service


class TestWorkspaceExecutionArtifactPromotionService:
    def test_successful_promotion(self):
        registry, integrity, service = _build()
        artifact = registry.register("runtime-1", "model.bin", "MODEL", "/artifacts/model.bin")

        promotion = service.promote(artifact.artifact_id, "version-1", "DEV")

        assert isinstance(promotion, WorkspaceExecutionArtifactPromotion)
        assert promotion.artifact_id == artifact.artifact_id
        assert promotion.version_id == "version-1"
        assert promotion.source_stage is None
        assert promotion.target_stage == "DEV"
        assert promotion.status == "ACTIVE"

        next_promotion = service.promote(artifact.artifact_id, "version-1", "STAGING")

        assert next_promotion.source_stage == "DEV"
        assert next_promotion.target_stage == "STAGING"

    def test_integrity_failure(self):
        registry, integrity, service = _build()
        artifact = registry.register("runtime-1", "dataset", "DATASET", "/artifacts/dataset")

        with pytest.raises(Error):
            service.promote(artifact.artifact_id, "unverified-version", "DEV")

    def test_invalid_stage_transition(self):
        registry, integrity, service = _build()
        artifact = registry.register("runtime-1", "model", "MODEL", "/artifacts/model")

        service.promote(artifact.artifact_id, "version-1", "STAGING")

        with pytest.raises(Error):
            service.promote(artifact.artifact_id, "version-1", "DEV")

        with pytest.raises(Error):
            service.promote(artifact.artifact_id, "version-1", "STAGING")

        with pytest.raises(Error):
            service.promote(artifact.artifact_id, "version-1", "UNKNOWN_STAGE")

    def test_production_immutability(self):
        registry, integrity, service = _build()
        artifact = registry.register("runtime-1", "model", "MODEL", "/artifacts/model")

        service.promote(artifact.artifact_id, "version-1", "STAGING")
        production = service.promote(artifact.artifact_id, "version-1", "PRODUCTION")

        with pytest.raises(Error):
            service.promote(artifact.artifact_id, "version-1", "PRODUCTION")

        with pytest.raises(Error):
            service.rollback(production.promotion_id)

    def test_rollback(self):
        registry, integrity, service = _build()
        artifact = registry.register("runtime-1", "dataset", "DATASET", "/artifacts/dataset")

        promotion = service.promote(artifact.artifact_id, "version-1", "STAGING")

        rolled_back = service.rollback(promotion.promotion_id)

        assert rolled_back.status == "ROLLED_BACK"
        assert service.status(promotion.promotion_id).status == "ROLLED_BACK"

        with pytest.raises(Error):
            service.rollback(promotion.promotion_id)

        again = service.promote(artifact.artifact_id, "version-1", "STAGING")
        assert again.source_stage is None

    def test_promotion_history(self):
        registry, integrity, service = _build()
        artifact = registry.register("runtime-1", "model", "MODEL", "/artifacts/model")

        first = service.promote(artifact.artifact_id, "version-1", "DEV")
        second = service.promote(artifact.artifact_id, "version-1", "STAGING")
        third = service.promote(artifact.artifact_id, "version-1", "PRODUCTION")

        history = service.history(artifact.artifact_id)

        assert history == (first, second, third)
