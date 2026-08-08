import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ArtifactBundleIntegrity,
    ExecutionArtifact,
    ExecutionArtifactBundleIntegrityError as Error,
    ExecutionArtifactBundleIntegrityService,
    ExecutionArtifactBundleService,
    ExecutionArtifactIntegrityService,
    ExecutionArtifactService,
    ExecutionArtifactVersionService,
)


class _VersionRegistry:
    def __init__(self):
        self._versions_by_id = {}

    def track(self, version):
        self._versions_by_id[version.version_id] = version
        return version

    def resolve(self, version_id):
        version = self._versions_by_id.get(version_id)

        if version is None:
            raise KeyError(version_id)

        return version


def _build_bundle():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    version_service = ExecutionArtifactVersionService(artifact_service)
    integrity_service = ExecutionArtifactIntegrityService()
    registry = _VersionRegistry()
    bundle_service = ExecutionArtifactBundleService(registry, integrity_service)

    pipeline_service.create(
        Pipeline(
            pipeline_id="pipeline-1",
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )
    session = session_service.start("pipeline-1", owner="user-1")

    artifact_service.register(
        session.session_id,
        ExecutionArtifact(
            artifact_id="artifact-a",
            session_id=session.session_id,
            name="artifact-a.log",
            type="log",
            location="/tmp/artifact-a.log",
        ),
    )
    version = registry.track(version_service.create("artifact-a", "/tmp/artifact-a-v1.log"))

    bundle = bundle_service.create(session.session_id, [version.version_id])
    bundle_integrity_service = ExecutionArtifactBundleIntegrityService(bundle_service)

    return bundle, bundle_integrity_service


class TestExecutionArtifactBundleIntegrityService:
    def test_record_checksum(self):
        bundle, bundle_integrity_service = _build_bundle()

        recorded = bundle_integrity_service.record(bundle.bundle_id, "abc123", algorithm="SHA256")

        assert isinstance(recorded, ArtifactBundleIntegrity)
        assert recorded.bundle_id == bundle.bundle_id
        assert recorded.checksum == "abc123"
        assert recorded.algorithm == "SHA256"
        assert bundle_integrity_service.status(bundle.bundle_id) == recorded

    def test_successful_verification(self):
        bundle, bundle_integrity_service = _build_bundle()
        bundle_integrity_service.record(bundle.bundle_id, "abc123", algorithm="SHA256")

        assert bundle_integrity_service.verify(bundle.bundle_id, "abc123") is True

    def test_mismatch_detection(self):
        bundle, bundle_integrity_service = _build_bundle()
        bundle_integrity_service.record(bundle.bundle_id, "abc123", algorithm="SHA256")

        assert bundle_integrity_service.verify(bundle.bundle_id, "tampered") is False
        assert bundle_integrity_service.status(bundle.bundle_id).checksum == "abc123"

    def test_algorithm_validation(self):
        bundle, bundle_integrity_service = _build_bundle()

        bundle_integrity_service.record(bundle.bundle_id, "abc123", algorithm="sha512")
        assert bundle_integrity_service.status(bundle.bundle_id).algorithm == "SHA512"

        with pytest.raises(Error):
            bundle_integrity_service.record(bundle.bundle_id, "def456", algorithm="MD5")

    def test_rejects_unknown_bundle(self):
        _bundle, bundle_integrity_service = _build_bundle()

        with pytest.raises(Error):
            bundle_integrity_service.verify("unknown-bundle", "abc123")

        with pytest.raises(Error):
            bundle_integrity_service.status("unknown-bundle")
