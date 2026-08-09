import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactService,
    ExecutionArtifactSignature,
    ExecutionArtifactSigningError as Error,
    ExecutionArtifactSigningService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    signing_service = ExecutionArtifactSigningService(artifact_service)

    pipeline_service.create(
        Pipeline(
            pipeline_id="pipeline-1",
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )
    session = session_service.start("pipeline-1", owner="user-1")

    return artifact_service, signing_service, session


def _register_artifact(artifact_service, session, artifact_id="artifact-1"):
    return artifact_service.register(
        session.session_id,
        ExecutionArtifact(
            artifact_id=artifact_id,
            session_id=session.session_id,
            name=f"{artifact_id}.log",
            type="log",
            location=f"/tmp/{artifact_id}.log",
        ),
    )


class TestExecutionArtifactSigningService:
    def test_sign_artifact(self):
        artifact_service, signing_service, session = _build()
        artifact = _register_artifact(artifact_service, session)

        signature = signing_service.sign(artifact.artifact_id, "key-1")

        assert isinstance(signature, ExecutionArtifactSignature)
        assert signature.algorithm == "SHA256"
        assert signature.key_id == "key-1"
        assert signature.signature != ""

    def test_verify_signature(self):
        artifact_service, signing_service, session = _build()
        artifact = _register_artifact(artifact_service, session)
        signed = signing_service.sign(artifact.artifact_id, "key-1")

        assert signing_service.verify(artifact.artifact_id, signed.signature) is True

    def test_invalid_signature(self):
        artifact_service, signing_service, session = _build()
        artifact = _register_artifact(artifact_service, session)
        signing_service.sign(artifact.artifact_id, "key-1")

        assert signing_service.verify(artifact.artifact_id, "tampered-signature") is False

    def test_duplicate_signature_rejection(self):
        artifact_service, signing_service, session = _build()
        artifact = _register_artifact(artifact_service, session)
        signing_service.sign(artifact.artifact_id, "key-1")

        with pytest.raises(Error):
            signing_service.sign(artifact.artifact_id, "key-2")

    def test_missing_key_rejection(self):
        artifact_service, signing_service, session = _build()
        artifact = _register_artifact(artifact_service, session)

        with pytest.raises(Error):
            signing_service.sign(artifact.artifact_id, "")

        with pytest.raises(Error):
            signing_service.sign(artifact.artifact_id, None)

    def test_signing_status(self):
        artifact_service, signing_service, session = _build()
        artifact = _register_artifact(artifact_service, session)

        with pytest.raises(Error):
            signing_service.status(artifact.artifact_id)

        signing_service.sign(artifact.artifact_id, "key-1")
        status = signing_service.status(artifact.artifact_id)

        assert isinstance(status, ExecutionArtifactSignature)
        assert status.key_id == "key-1"
