import pytest

from backend.session import (
    ArtifactPromotion,
    ExecutionArtifactIntegrityService,
    ExecutionArtifactPromotionError as Error,
    ExecutionArtifactPromotionService,
)


def _build():
    integrity_service = ExecutionArtifactIntegrityService()
    promotion_service = ExecutionArtifactPromotionService(integrity_service)
    return integrity_service, promotion_service


def _verify(integrity_service, version_id="version-1"):
    integrity_service.record(version_id, "abc123", algorithm="SHA256")


class TestExecutionArtifactPromotionService:
    def test_successful_promotion(self):
        integrity_service, promotion_service = _build()
        _verify(integrity_service)

        promotion = promotion_service.promote("version-1", "staging", artifact_id="artifact-1")

        assert isinstance(promotion, ArtifactPromotion)
        assert promotion.version_id == "version-1"
        assert promotion.target == "staging"
        assert promotion.source is None

    def test_unverified_rejection(self):
        _integrity_service, promotion_service = _build()

        with pytest.raises(Error):
            promotion_service.promote("version-1", "staging", artifact_id="artifact-1")

    def test_duplicate_target_rejection(self):
        integrity_service, promotion_service = _build()
        _verify(integrity_service)

        promotion_service.promote("version-1", "staging", artifact_id="artifact-1")

        with pytest.raises(Error):
            promotion_service.promote("version-1", "staging", artifact_id="artifact-1")

    def test_history_ordering(self):
        integrity_service, promotion_service = _build()
        _verify(integrity_service)

        first = promotion_service.promote("version-1", "staging", artifact_id="artifact-1")
        second = promotion_service.promote("version-1", "production", artifact_id="artifact-1")

        history = promotion_service.history("version-1")

        assert history == [first, second]
        assert first.source is None
        assert second.source == "staging"

    def test_current_environment_lookup(self):
        integrity_service, promotion_service = _build()
        _verify(integrity_service)

        promotion_service.promote("version-1", "staging", artifact_id="artifact-1")
        production = promotion_service.promote("version-1", "production", artifact_id="artifact-1")

        assert promotion_service.current("artifact-1", "production") == production

        with pytest.raises(Error):
            promotion_service.current("artifact-1", "canary")
