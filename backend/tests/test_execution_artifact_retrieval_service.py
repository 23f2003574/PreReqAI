import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactAccessService,
    ExecutionArtifactRetrievalError as Error,
    ExecutionArtifactRetrievalRequest,
    ExecutionArtifactRetrievalResult,
    ExecutionArtifactRetrievalService,
    ExecutionArtifactService,
    ExecutionArtifactVersionService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    version_service = ExecutionArtifactVersionService(artifact_service)
    access_service = ExecutionArtifactAccessService(artifact_service)
    retrieval_service = ExecutionArtifactRetrievalService(artifact_service, version_service, access_service)
    return pipeline_service, session_service, artifact_service, version_service, access_service, retrieval_service


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


class TestExecutionArtifactRetrievalService:
    def test_latest_retrieval(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, retrieval_service = (
            _build()
        )
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
        version_service.create(artifact.artifact_id, "/tmp/output-v2.log")
        access_service.grant(artifact.artifact_id, "user-1", "READ")

        result = retrieval_service.retrieve(
            ExecutionArtifactRetrievalRequest(artifact_id=artifact.artifact_id, consumer="user-1")
        )

        assert isinstance(result, ExecutionArtifactRetrievalResult)
        assert result.version == 2
        assert result.location == "/tmp/output-v2.log"

        via_latest = retrieval_service.latest(artifact.artifact_id)
        assert via_latest == result

    def test_explicit_version(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, retrieval_service = (
            _build()
        )
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
        version_service.create(artifact.artifact_id, "/tmp/output-v2.log")
        access_service.grant(artifact.artifact_id, "user-1", "READ")

        result = retrieval_service.retrieve(
            ExecutionArtifactRetrievalRequest(artifact_id=artifact.artifact_id, consumer="user-1", version=1)
        )

        assert result.version == 1
        assert result.location == "/tmp/output-v1.log"

        via_version = retrieval_service.version(artifact.artifact_id, 1)
        assert via_version == result

    def test_unauthorized_retrieval(self):
        pipeline_service, session_service, artifact_service, version_service, _access_service, retrieval_service = (
            _build()
        )
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v1.log")

        with pytest.raises(Error):
            retrieval_service.retrieve(
                ExecutionArtifactRetrievalRequest(artifact_id=artifact.artifact_id, consumer="user-1")
            )

    def test_missing_version(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, retrieval_service = (
            _build()
        )
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
        access_service.grant(artifact.artifact_id, "user-1", "READ")

        with pytest.raises(Error):
            retrieval_service.retrieve(
                ExecutionArtifactRetrievalRequest(artifact_id=artifact.artifact_id, consumer="user-1", version=99)
            )

        with pytest.raises(Error):
            retrieval_service.version(artifact.artifact_id, 99)

    def test_no_versions_available(self):
        pipeline_service, session_service, artifact_service, _version_service, access_service, retrieval_service = (
            _build()
        )
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        access_service.grant(artifact.artifact_id, "user-1", "READ")

        with pytest.raises(Error):
            retrieval_service.retrieve(
                ExecutionArtifactRetrievalRequest(artifact_id=artifact.artifact_id, consumer="user-1")
            )

    def test_unknown_artifact(self):
        *_rest, retrieval_service = _build()

        with pytest.raises(Error):
            retrieval_service.retrieve(
                ExecutionArtifactRetrievalRequest(artifact_id="unknown-artifact", consumer="user-1")
            )

        with pytest.raises(Error):
            retrieval_service.latest("unknown-artifact")

        with pytest.raises(Error):
            retrieval_service.version("unknown-artifact", 1)

    def test_retrieve_never_mutates_artifacts(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, retrieval_service = (
            _build()
        )
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
        access_service.grant(artifact.artifact_id, "user-1", "READ")

        retrieval_service.retrieve(
            ExecutionArtifactRetrievalRequest(artifact_id=artifact.artifact_id, consumer="user-1")
        )

        assert artifact_service.get(artifact.artifact_id) == artifact

    def test_rejects_invalid_request(self):
        *_rest, retrieval_service = _build()

        with pytest.raises(Error):
            retrieval_service.retrieve("not-a-request")
