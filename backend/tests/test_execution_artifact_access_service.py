import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ArtifactAccessResult,
    ArtifactPermission,
    ExecutionArtifact,
    ExecutionArtifactAccessError as Error,
    ExecutionArtifactAccessService,
    ExecutionArtifactService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    access_service = ExecutionArtifactAccessService(artifact_service)
    return pipeline_service, session_service, artifact_service, access_service


def _create_pipeline(pipeline_service, pipeline_id):
    pipeline_service.create(
        Pipeline(
            pipeline_id=pipeline_id,
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )


def _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1"):
    _create_pipeline(pipeline_service, pipeline_id)
    return session_service.start(pipeline_id, owner=owner)


def _register_artifact(artifact_service, session_id, artifact_id="artifact-1"):
    return artifact_service.register(
        session_id,
        ExecutionArtifact(
            artifact_id=artifact_id,
            session_id=session_id,
            name="output.log",
            type="log",
            location="/tmp/output.log",
        ),
    )


class TestExecutionArtifactAccessService:
    def test_grant_and_authorize(self):
        pipeline_service, session_service, artifact_service, access_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        granted = access_service.grant(artifact.artifact_id, "user-1", "read")

        assert isinstance(granted, ArtifactPermission)
        assert granted.operation == "READ"

        result = access_service.authorize(artifact.artifact_id, "user-1", "READ")

        assert isinstance(result, ArtifactAccessResult)
        assert result.allowed is True

    def test_default_denial(self):
        pipeline_service, session_service, artifact_service, access_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        result = access_service.authorize(artifact.artifact_id, "user-1", "READ")

        assert isinstance(result, ArtifactAccessResult)
        assert result.allowed is False

    def test_revoke(self):
        pipeline_service, session_service, artifact_service, access_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        access_service.grant(artifact.artifact_id, "user-1", "DELETE")
        assert access_service.authorize(artifact.artifact_id, "user-1", "DELETE").allowed is True

        access_service.revoke(artifact.artifact_id, "user-1", "DELETE")
        assert access_service.authorize(artifact.artifact_id, "user-1", "DELETE").allowed is False

    def test_operation_isolation(self):
        pipeline_service, session_service, artifact_service, access_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        access_service.grant(artifact.artifact_id, "user-1", "READ")

        assert access_service.authorize(artifact.artifact_id, "user-1", "READ").allowed is True
        assert access_service.authorize(artifact.artifact_id, "user-1", "PROMOTE").allowed is False
        assert access_service.authorize(artifact.artifact_id, "user-1", "DELETE").allowed is False

    def test_permission_listing(self):
        pipeline_service, session_service, artifact_service, access_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        access_service.grant(artifact.artifact_id, "user-1", "READ")
        access_service.grant(artifact.artifact_id, "user-2", "PROMOTE")

        listed = access_service.permissions(artifact.artifact_id)

        assert [(entry.principal, entry.operation) for entry in listed] == [
            ("user-1", "READ"),
            ("user-2", "PROMOTE"),
        ]

    def test_rejects_unknown_artifact(self):
        _pipeline_service, _session_service, _artifact_service, access_service = _build()

        with pytest.raises(Error):
            access_service.grant("unknown-artifact", "user-1", "READ")

        with pytest.raises(Error):
            access_service.authorize("unknown-artifact", "user-1", "READ")
