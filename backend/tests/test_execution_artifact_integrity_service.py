import pytest

from backend.session import (
    ExecutionArtifactIntegrity,
    ExecutionArtifactIntegrityError as Error,
    ExecutionArtifactIntegrityService,
)


class TestExecutionArtifactIntegrityService:
    def test_record_checksum(self):
        service = ExecutionArtifactIntegrityService()

        recorded = service.record("version-1", "abc123", algorithm="SHA256")

        assert isinstance(recorded, ExecutionArtifactIntegrity)
        assert recorded.version_id == "version-1"
        assert recorded.checksum == "abc123"
        assert recorded.algorithm == "SHA256"
        assert service.status("version-1") == recorded

    def test_successful_verification(self):
        service = ExecutionArtifactIntegrityService()
        service.record("version-1", "abc123", algorithm="SHA256")

        assert service.verify("version-1", "abc123") is True
        assert service.status("version-1").checksum == "abc123"

    def test_mismatch_detection(self):
        service = ExecutionArtifactIntegrityService()
        service.record("version-1", "abc123", algorithm="SHA256")

        assert service.verify("version-1", "tampered") is False
        assert service.status("version-1").checksum == "abc123"

    def test_algorithm_validation(self):
        service = ExecutionArtifactIntegrityService()

        service.record("version-1", "abc123", algorithm="sha512")
        assert service.status("version-1").algorithm == "SHA512"

        with pytest.raises(Error):
            service.record("version-2", "def456", algorithm="MD5")

    def test_rejects_unknown_version(self):
        service = ExecutionArtifactIntegrityService()

        with pytest.raises(Error):
            service.verify("unknown-version", "abc123")

        with pytest.raises(Error):
            service.status("unknown-version")
