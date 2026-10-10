import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ArtifactPublication,
    ExecutionArtifact,
    ExecutionArtifactDistributionChannel,
    ExecutionArtifactDistributionError as Error,
    ExecutionArtifactDistributionService,
    ExecutionArtifactService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    distribution_service = ExecutionArtifactDistributionService(artifact_service)
    return pipeline_service, session_service, artifact_service, distribution_service


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


def _channel(channel_id="channel-1", enabled=True):
    return ExecutionArtifactDistributionChannel(
        channel_id=channel_id,
        name="Primary Webhook",
        type="webhook",
        endpoint="https://example.test/hooks/artifacts",
        enabled=enabled,
    )


class TestExecutionArtifactDistributionService:
    def test_register_channel(self):
        _pipeline_service, _session_service, _artifact_service, distribution_service = _build()

        registered = distribution_service.register(_channel())

        assert isinstance(registered, ExecutionArtifactDistributionChannel)
        assert registered in distribution_service.channels()

    def test_publish_artifact(self):
        pipeline_service, session_service, artifact_service, distribution_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        distribution_service.register(_channel())

        publication = distribution_service.publish(artifact.artifact_id, "channel-1")

        assert isinstance(publication, ArtifactPublication)
        assert publication.artifact_id == artifact.artifact_id
        assert publication.channel_id == "channel-1"
        assert publication.status == "PUBLISHED"

    def test_disabled_channel_rejection(self):
        pipeline_service, session_service, artifact_service, distribution_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        distribution_service.register(_channel())

        distribution_service.disable("channel-1")

        with pytest.raises(Error):
            distribution_service.publish(artifact.artifact_id, "channel-1")

    def test_duplicate_channel_rejection(self):
        _pipeline_service, _session_service, _artifact_service, distribution_service = _build()
        distribution_service.register(_channel())

        with pytest.raises(Error):
            distribution_service.register(_channel())

    def test_status_lookup(self):
        pipeline_service, session_service, artifact_service, distribution_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        distribution_service.register(_channel())

        distribution_service.publish(artifact.artifact_id, "channel-1")

        status = distribution_service.status("channel-1")

        assert isinstance(status, ArtifactPublication)
        assert status.channel_id == "channel-1"
        assert status.artifact_id == artifact.artifact_id
