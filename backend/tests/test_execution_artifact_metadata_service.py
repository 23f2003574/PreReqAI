import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactService,
    ExecutionArtifactMetadata,
    ExecutionArtifactMetadataError as Error,
    ExecutionArtifactMetadataService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    metadata_service = ExecutionArtifactMetadataService(artifact_service)
    return pipeline_service, session_service, artifact_service, metadata_service


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


class TestExecutionArtifactMetadataService:
    def test_set_and_get_metadata(self):
        pipeline_service, session_service, artifact_service, metadata_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        metadata_service.set(artifact.artifact_id, "size", "1024")
        entry = metadata_service.get(artifact.artifact_id, "size")

        assert isinstance(entry, ExecutionArtifactMetadata)
        assert entry.value == "1024"

    def test_overwrite_metadata(self):
        pipeline_service, session_service, artifact_service, metadata_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        metadata_service.set(artifact.artifact_id, "size", "1024")
        metadata_service.set(artifact.artifact_id, "size", "2048")

        assert metadata_service.get(artifact.artifact_id, "size").value == "2048"

    def test_remove_metadata(self):
        pipeline_service, session_service, artifact_service, metadata_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        metadata_service.set(artifact.artifact_id, "size", "1024")
        removed = metadata_service.remove(artifact.artifact_id, "size")

        assert removed.value == "1024"

        with pytest.raises(Error):
            metadata_service.get(artifact.artifact_id, "size")

    def test_add_and_find_tags(self):
        pipeline_service, session_service, artifact_service, metadata_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact_a = _register_artifact(artifact_service, session.session_id, artifact_id="artifact-a")
        artifact_b = _register_artifact(artifact_service, session.session_id, artifact_id="artifact-b")

        metadata_service.tag(artifact_a.artifact_id, "important")
        metadata_service.tag(artifact_b.artifact_id, "important")

        tags = metadata_service.tags(artifact_a.artifact_id)
        assert [entry.tag for entry in tags] == ["important"]

        matches = metadata_service.find("important")
        assert sorted(entry.artifact_id for entry in matches) == ["artifact-a", "artifact-b"]

    def test_rejects_duplicate_tag(self):
        pipeline_service, session_service, artifact_service, metadata_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        metadata_service.tag(artifact.artifact_id, "important")

        with pytest.raises(Error):
            metadata_service.tag(artifact.artifact_id, "important")

    def test_rejects_unknown_artifact(self):
        _pipeline_service, _session_service, _artifact_service, metadata_service = _build()

        with pytest.raises(Error):
            metadata_service.set("unknown-artifact", "size", "1024")

        with pytest.raises(Error):
            metadata_service.tag("unknown-artifact", "important")
