import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactService,
    ExecutionArtifactVersion,
    ExecutionArtifactVersionError as Error,
    ExecutionArtifactVersionService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    version_service = ExecutionArtifactVersionService(artifact_service)
    return pipeline_service, session_service, artifact_service, version_service


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


class TestExecutionArtifactVersionService:
    def test_create_version_starts_at_one(self):
        pipeline_service, session_service, artifact_service, version_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        created = version_service.create(artifact.artifact_id, "/tmp/output-v1.log")

        assert isinstance(created, ExecutionArtifactVersion)
        assert created.version == 1
        assert created.artifact_id == artifact.artifact_id

    def test_latest_lookup(self):
        pipeline_service, session_service, artifact_service, version_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
        second = version_service.create(artifact.artifact_id, "/tmp/output-v2.log")

        assert version_service.latest(artifact.artifact_id) == second
        assert version_service.get(artifact.artifact_id, 2) == second

    def test_history_ordering(self):
        pipeline_service, session_service, artifact_service, version_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
        version_service.create(artifact.artifact_id, "/tmp/output-v2.log")
        version_service.create(artifact.artifact_id, "/tmp/output-v3.log")

        history = version_service.history(artifact.artifact_id)

        assert [entry.version for entry in history] == [1, 2, 3]

    def test_versions_are_immutable(self):
        pipeline_service, session_service, artifact_service, version_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        created = version_service.create(artifact.artifact_id, "/tmp/output-v1.log")

        with pytest.raises(dataclasses.FrozenInstanceError):
            created.location = "/tmp/tampered.log"

        assert version_service.get(artifact.artifact_id, 1).location == "/tmp/output-v1.log"

    def test_rejects_duplicate_version_number(self):
        pipeline_service, session_service, artifact_service, version_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)

        version_service.create(artifact.artifact_id, "/tmp/output-v1.log", version=1)

        with pytest.raises(Error):
            version_service.create(artifact.artifact_id, "/tmp/other-v1.log", version=1)
