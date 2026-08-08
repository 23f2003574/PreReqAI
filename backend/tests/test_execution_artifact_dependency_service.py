import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ArtifactDependency,
    ArtifactDependencyResult,
    ExecutionArtifact,
    ExecutionArtifactDependencyError as Error,
    ExecutionArtifactDependencyService,
    ExecutionArtifactService,
    ExecutionArtifactVersionService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    version_service = ExecutionArtifactVersionService(artifact_service)
    dependency_service = ExecutionArtifactDependencyService(artifact_service, version_service)
    return pipeline_service, session_service, artifact_service, version_service, dependency_service


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


def _register_artifact(artifact_service, session_id, artifact_id):
    return artifact_service.register(
        session_id,
        ExecutionArtifact(
            artifact_id=artifact_id,
            session_id=session_id,
            name=f"{artifact_id}.log",
            type="log",
            location=f"/tmp/{artifact_id}.log",
        ),
    )


class TestExecutionArtifactDependencyService:
    def test_add_and_remove_dependency(self):
        pipeline_service, session_service, artifact_service, version_service, dependency_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        _register_artifact(artifact_service, session.session_id, "artifact-b")

        added = dependency_service.add("artifact-a", "artifact-b")

        assert isinstance(added, ArtifactDependency)
        assert added.artifact_id == "artifact-a"
        assert added.required_artifact_id == "artifact-b"

        removed = dependency_service.remove(added.dependency_id)
        assert removed == added
        assert dependency_service.dependents("artifact-b") == []

    def test_satisfied_dependency(self):
        pipeline_service, session_service, artifact_service, version_service, dependency_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        _register_artifact(artifact_service, session.session_id, "artifact-b")
        version_service.create("artifact-b", "/tmp/artifact-b-v1.log")

        dependency_service.add("artifact-a", "artifact-b")

        result = dependency_service.validate("artifact-a")

        assert isinstance(result, ArtifactDependencyResult)
        assert result.satisfied is True

    def test_missing_dependency(self):
        pipeline_service, session_service, artifact_service, version_service, dependency_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        _register_artifact(artifact_service, session.session_id, "artifact-b")

        dependency_service.add("artifact-a", "artifact-b")

        result = dependency_service.validate("artifact-a")

        assert result.satisfied is False

    def test_version_mismatch(self):
        pipeline_service, session_service, artifact_service, version_service, dependency_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        _register_artifact(artifact_service, session.session_id, "artifact-b")
        version_service.create("artifact-b", "/tmp/artifact-b-v1.log")

        dependency_service.add("artifact-a", "artifact-b", version=2)

        result = dependency_service.validate("artifact-a")

        assert result.satisfied is False

    def test_cycle_detection(self):
        pipeline_service, session_service, artifact_service, version_service, dependency_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        _register_artifact(artifact_service, session.session_id, "artifact-b")

        dependency_service.add("artifact-a", "artifact-b")

        with pytest.raises(Error):
            dependency_service.add("artifact-b", "artifact-a")

        with pytest.raises(Error):
            dependency_service.add("artifact-a", "artifact-a")

    def test_dependent_lookup(self):
        pipeline_service, session_service, artifact_service, version_service, dependency_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        _register_artifact(artifact_service, session.session_id, "artifact-b")
        _register_artifact(artifact_service, session.session_id, "artifact-c")

        dependency_service.add("artifact-a", "artifact-c")
        dependency_service.add("artifact-b", "artifact-c")

        assert dependency_service.dependents("artifact-c") == ["artifact-a", "artifact-b"]
