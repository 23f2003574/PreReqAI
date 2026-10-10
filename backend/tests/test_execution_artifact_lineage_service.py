import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ArtifactLineage,
    ExecutionArtifact,
    ExecutionArtifactLineageError as Error,
    ExecutionArtifactLineageService,
    ExecutionArtifactService,
    ExecutionArtifactVersionService,
)


class _VersionRegistry:
    """
    Minimal stand-in for a version-ID resolver, satisfying the
    duck-typed `resolve(version_id)` contract the lineage service
    depends on, by indexing real ExecutionArtifactVersion objects as
    they are created.
    """

    def __init__(self):
        self._versions_by_id = {}

    def track(self, version):
        self._versions_by_id[version.version_id] = version
        return version

    def resolve(self, version_id):
        version = self._versions_by_id.get(version_id)

        if version is None:
            raise KeyError(version_id)

        return version


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    version_service = ExecutionArtifactVersionService(artifact_service)
    registry = _VersionRegistry()
    lineage_service = ExecutionArtifactLineageService(registry)
    return pipeline_service, session_service, artifact_service, version_service, registry, lineage_service


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


class TestExecutionArtifactLineageService:
    def test_record_lineage(self):
        pipeline_service, session_service, artifact_service, version_service, registry, lineage_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        _register_artifact(artifact_service, session.session_id, "artifact-b")
        source = registry.track(version_service.create("artifact-a", "/tmp/a-v1.log"))
        output = registry.track(version_service.create("artifact-b", "/tmp/b-v1.log"))

        recorded = lineage_service.record(output.version_id, [source.version_id], session.session_id)

        assert isinstance(recorded, ArtifactLineage)
        assert recorded.output_version_id == output.version_id
        assert recorded.input_version_ids == (source.version_id,)

    def test_input_lookup(self):
        pipeline_service, session_service, artifact_service, version_service, registry, lineage_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        _register_artifact(artifact_service, session.session_id, "artifact-b")
        source = registry.track(version_service.create("artifact-a", "/tmp/a-v1.log"))
        output = registry.track(version_service.create("artifact-b", "/tmp/b-v1.log"))

        lineage_service.record(output.version_id, [source.version_id], session.session_id)

        assert lineage_service.inputs(output.version_id) == (source.version_id,)

    def test_output_lookup(self):
        pipeline_service, session_service, artifact_service, version_service, registry, lineage_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        _register_artifact(artifact_service, session.session_id, "artifact-b")
        source = registry.track(version_service.create("artifact-a", "/tmp/a-v1.log"))
        output = registry.track(version_service.create("artifact-b", "/tmp/b-v1.log"))

        lineage_service.record(output.version_id, [source.version_id], session.session_id)

        assert lineage_service.outputs(source.version_id) == [output.version_id]

    def test_missing_input_rejection(self):
        pipeline_service, session_service, artifact_service, version_service, registry, lineage_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-b")
        output = registry.track(version_service.create("artifact-b", "/tmp/b-v1.log"))

        with pytest.raises(Error):
            lineage_service.record(output.version_id, ["unknown-version"], session.session_id)

    def test_self_lineage_rejection(self):
        pipeline_service, session_service, artifact_service, version_service, registry, lineage_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        output = registry.track(version_service.create("artifact-a", "/tmp/a-v1.log"))

        with pytest.raises(Error):
            lineage_service.record(output.version_id, [output.version_id], session.session_id)

    def test_immutable_history(self):
        pipeline_service, session_service, artifact_service, version_service, registry, lineage_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        _register_artifact(artifact_service, session.session_id, "artifact-b")
        source = registry.track(version_service.create("artifact-a", "/tmp/a-v1.log"))
        output = registry.track(version_service.create("artifact-b", "/tmp/b-v1.log"))

        recorded = lineage_service.record(output.version_id, [source.version_id], session.session_id)

        with pytest.raises(dataclasses.FrozenInstanceError):
            recorded.session_id = "tampered"

        assert lineage_service.lineage(output.version_id) == recorded
