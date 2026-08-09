import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactEncryption,
    ExecutionArtifactEncryptionError as Error,
    ExecutionArtifactEncryptionService,
    ExecutionArtifactService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    encryption_service = ExecutionArtifactEncryptionService(artifact_service)

    pipeline_service.create(
        Pipeline(
            pipeline_id="pipeline-1",
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )
    session = session_service.start("pipeline-1", owner="user-1")

    return artifact_service, encryption_service, session


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


class TestExecutionArtifactEncryptionService:
    def test_encrypt_artifact(self):
        artifact_service, encryption_service, session = _build()
        artifact = _register_artifact(artifact_service, session)

        encryption = encryption_service.encrypt(artifact.artifact_id, "key-1")

        assert isinstance(encryption, ExecutionArtifactEncryption)
        assert encryption.algorithm == "AES256"
        assert encryption.key_id == "key-1"
        assert encryption.encrypted is True

    def test_encryption_status(self):
        artifact_service, encryption_service, session = _build()
        artifact = _register_artifact(artifact_service, session)
        encryption_service.encrypt(artifact.artifact_id, "key-1")

        status = encryption_service.status(artifact.artifact_id)

        assert isinstance(status, ExecutionArtifactEncryption)
        assert status.key_id == "key-1"

    def test_verify_encryption(self):
        artifact_service, encryption_service, session = _build()
        artifact = _register_artifact(artifact_service, session)
        encryption_service.encrypt(artifact.artifact_id, "key-1")

        assert encryption_service.verify(artifact.artifact_id) is True

    def test_decrypt(self):
        artifact_service, encryption_service, session = _build()
        artifact = _register_artifact(artifact_service, session)
        encryption_service.encrypt(artifact.artifact_id, "key-1")

        decrypted = encryption_service.decrypt(artifact.artifact_id)

        assert decrypted.encrypted is False
        assert decrypted.encrypted_at is None

    def test_invalid_key_rejection(self):
        artifact_service, encryption_service, session = _build()
        artifact = _register_artifact(artifact_service, session)

        with pytest.raises(Error):
            encryption_service.encrypt(artifact.artifact_id, "")

        with pytest.raises(Error):
            encryption_service.encrypt(artifact.artifact_id, None)

    def test_unencrypted_distribution_rejection(self):
        artifact_service, encryption_service, session = _build()
        artifact = _register_artifact(artifact_service, session)

        with pytest.raises(Error):
            encryption_service.verify(artifact.artifact_id)

        encryption_service.encrypt(artifact.artifact_id, "key-1")
        encryption_service.decrypt(artifact.artifact_id)

        with pytest.raises(Error):
            encryption_service.verify(artifact.artifact_id)
