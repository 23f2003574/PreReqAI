import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactError as Error,
    ExecutionArtifactService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    return pipeline_service, session_service, artifact_service


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


def _artifact(artifact_id, session_id, name="output.log", type="log", location="/tmp/output.log"):
    return ExecutionArtifact(
        artifact_id=artifact_id,
        session_id=session_id,
        name=name,
        type=type,
        location=location,
    )


class TestExecutionArtifactService:
    def test_register_and_get(self):
        pipeline_service, session_service, artifact_service = _build()
        session = _start_session(pipeline_service, session_service)

        registered = artifact_service.register(session.session_id, _artifact("artifact-1", session.session_id))

        assert registered.artifact_id == "artifact-1"
        assert artifact_service.get("artifact-1") == registered

    def test_list_preserves_registration_order(self):
        pipeline_service, session_service, artifact_service = _build()
        session = _start_session(pipeline_service, session_service)

        artifact_service.register(session.session_id, _artifact("artifact-3", session.session_id))
        artifact_service.register(session.session_id, _artifact("artifact-1", session.session_id))
        artifact_service.register(session.session_id, _artifact("artifact-2", session.session_id))

        listed = artifact_service.list(session.session_id)

        assert [artifact.artifact_id for artifact in listed] == ["artifact-3", "artifact-1", "artifact-2"]

    def test_remove_does_not_remove_session(self):
        pipeline_service, session_service, artifact_service = _build()
        session = _start_session(pipeline_service, session_service)

        artifact_service.register(session.session_id, _artifact("artifact-1", session.session_id))

        removed = artifact_service.remove("artifact-1")

        assert removed.artifact_id == "artifact-1"
        assert artifact_service.list(session.session_id) == []

        with pytest.raises(Error):
            artifact_service.get("artifact-1")

    def test_rejects_duplicate_artifact_id(self):
        pipeline_service, session_service, artifact_service = _build()
        session = _start_session(pipeline_service, session_service)

        artifact_service.register(session.session_id, _artifact("artifact-1", session.session_id))

        with pytest.raises(Error):
            artifact_service.register(session.session_id, _artifact("artifact-1", session.session_id))

    def test_rejects_unknown_session(self):
        _pipeline_service, _session_service, artifact_service = _build()

        with pytest.raises(Error):
            artifact_service.register("unknown-session", _artifact("artifact-1", "unknown-session"))

        with pytest.raises(Error):
            artifact_service.list("unknown-session")
