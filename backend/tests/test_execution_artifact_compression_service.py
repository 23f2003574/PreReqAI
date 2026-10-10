import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactCompression,
    ExecutionArtifactCompressionError as Error,
    ExecutionArtifactCompressionService,
    ExecutionArtifactService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    compression_service = ExecutionArtifactCompressionService(artifact_service)

    pipeline_service.create(
        Pipeline(
            pipeline_id="pipeline-1",
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )
    session = session_service.start("pipeline-1", owner="user-1")

    return artifact_service, compression_service, session


def _register_artifact(artifact_service, session, artifact_id="artifact-1", location="/tmp/artifact-1.log"):
    return artifact_service.register(
        session.session_id,
        ExecutionArtifact(
            artifact_id=artifact_id,
            session_id=session.session_id,
            name=f"{artifact_id}.log",
            type="log",
            location=location,
        ),
    )


class TestExecutionArtifactCompressionService:
    def test_compress_artifact(self):
        artifact_service, compression_service, session = _build()
        artifact = _register_artifact(artifact_service, session)

        compression = compression_service.compress(artifact.artifact_id)

        assert isinstance(compression, ExecutionArtifactCompression)
        assert compression.algorithm == "GZIP"
        assert compression.compressed is True
        assert compression.compressed_size <= compression.original_size

    def test_size_tracking(self):
        artifact_service, compression_service, session = _build()
        artifact = _register_artifact(artifact_service, session, location="/tmp/artifact-1.log")

        compression = compression_service.compress(artifact.artifact_id)

        expected_original_size = len("/tmp/artifact-1.log".encode("utf-8"))

        assert compression.original_size == expected_original_size
        assert compression.compressed_size == max(1, expected_original_size // 2)

    def test_verify_compression(self):
        artifact_service, compression_service, session = _build()
        artifact = _register_artifact(artifact_service, session)
        compression_service.compress(artifact.artifact_id)

        assert compression_service.verify(artifact.artifact_id) is True

    def test_restore_artifact(self):
        artifact_service, compression_service, session = _build()
        artifact = _register_artifact(artifact_service, session)
        compressed = compression_service.compress(artifact.artifact_id)

        restored = compression_service.restore(artifact.artifact_id)

        assert restored.compressed is False
        assert restored.compressed_size is None
        assert restored.original_size == compressed.original_size

    def test_invalid_artifact_rejection(self):
        _artifact_service, compression_service, _session = _build()

        with pytest.raises(Error):
            compression_service.compress("unknown-artifact")

        with pytest.raises(Error):
            compression_service.verify("unknown-artifact")

    def test_compression_status(self):
        artifact_service, compression_service, session = _build()
        artifact = _register_artifact(artifact_service, session)

        with pytest.raises(Error):
            compression_service.status(artifact.artifact_id)

        compression_service.compress(artifact.artifact_id)
        status = compression_service.status(artifact.artifact_id)

        assert isinstance(status, ExecutionArtifactCompression)
        assert status.compressed is True
