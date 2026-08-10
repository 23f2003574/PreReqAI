import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactDiscoveryError as Error,
    ExecutionArtifactDiscoveryService,
    ExecutionArtifactMetadataService,
    ExecutionArtifactQuery,
    ExecutionArtifactSearchResult,
    ExecutionArtifactService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    metadata_service = ExecutionArtifactMetadataService(artifact_service)
    discovery_service = ExecutionArtifactDiscoveryService(artifact_service, metadata_service)
    return pipeline_service, session_service, artifact_service, metadata_service, discovery_service


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


def _register_artifact(artifact_service, session_id, artifact_id, type="log", name="output.log"):
    return artifact_service.register(
        session_id,
        ExecutionArtifact(
            artifact_id=artifact_id,
            session_id=session_id,
            name=name,
            type=type,
            location=f"/tmp/{artifact_id}",
        ),
    )


class TestExecutionArtifactDiscoveryService:
    def test_session_search(self):
        pipeline_service, session_service, artifact_service, _metadata_service, discovery_service = _build()
        session = _start_session(pipeline_service, session_service)
        first = _register_artifact(artifact_service, session.session_id, "artifact-1")
        second = _register_artifact(artifact_service, session.session_id, "artifact-2")

        results = discovery_service.by_session(session.session_id)

        assert [result.artifact_id for result in results] == [first.artifact_id, second.artifact_id]
        assert all(isinstance(result, ExecutionArtifactSearchResult) for result in results)

    def test_session_search_unknown_session_returns_empty(self):
        *_rest, discovery_service = _build()

        assert discovery_service.by_session("unknown-session") == []

    def test_type_search(self):
        pipeline_service, session_service, artifact_service, _metadata_service, discovery_service = _build()
        session = _start_session(pipeline_service, session_service)
        report = _register_artifact(artifact_service, session.session_id, "artifact-1", type="report")
        _register_artifact(artifact_service, session.session_id, "artifact-2", type="log")
        discovery_service.index(report.artifact_id)
        discovery_service.index("artifact-2")

        results = discovery_service.by_type("report")

        assert [result.artifact_id for result in results] == [report.artifact_id]

    def test_type_search_requires_indexing(self):
        pipeline_service, session_service, artifact_service, _metadata_service, discovery_service = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-1", type="report")

        assert discovery_service.by_type("report") == []

    def test_tag_search(self):
        pipeline_service, session_service, artifact_service, metadata_service, discovery_service = _build()
        session = _start_session(pipeline_service, session_service)
        first = _register_artifact(artifact_service, session.session_id, "artifact-1")
        second = _register_artifact(artifact_service, session.session_id, "artifact-2")
        metadata_service.tag(first.artifact_id, "reviewed")
        metadata_service.tag(second.artifact_id, "reviewed")

        results = discovery_service.by_tag("reviewed")

        assert [result.artifact_id for result in results] == [first.artifact_id, second.artifact_id]

    def test_tag_search_unknown_tag_returns_empty(self):
        *_rest, discovery_service = _build()

        assert discovery_service.by_tag("unknown-tag") == []

    def test_metadata_filtering(self):
        pipeline_service, session_service, artifact_service, metadata_service, discovery_service = _build()
        session = _start_session(pipeline_service, session_service)
        matching = _register_artifact(artifact_service, session.session_id, "artifact-1")
        other = _register_artifact(artifact_service, session.session_id, "artifact-2")
        metadata_service.set(matching.artifact_id, "size", "1024")
        metadata_service.set(other.artifact_id, "size", "2048")
        discovery_service.index(matching.artifact_id)
        discovery_service.index(other.artifact_id)

        results = discovery_service.search(ExecutionArtifactQuery(metadata={"size": "1024"}))

        assert [result.artifact_id for result in results] == [matching.artifact_id]

    def test_combined_filters(self):
        pipeline_service, session_service, artifact_service, metadata_service, discovery_service = _build()
        session = _start_session(pipeline_service, session_service)
        matching = _register_artifact(artifact_service, session.session_id, "artifact-1", type="report")
        wrong_type = _register_artifact(artifact_service, session.session_id, "artifact-2", type="log")
        metadata_service.tag(matching.artifact_id, "reviewed")
        metadata_service.tag(wrong_type.artifact_id, "reviewed")
        metadata_service.set(matching.artifact_id, "owner", "user-1")
        metadata_service.set(wrong_type.artifact_id, "owner", "user-1")

        results = discovery_service.search(
            ExecutionArtifactQuery(
                session_id=session.session_id,
                type="report",
                tag="reviewed",
                metadata={"owner": "user-1"},
            )
        )

        assert [result.artifact_id for result in results] == [matching.artifact_id]
        assert results[0].score == 4.0

    def test_deterministic_ordering(self):
        pipeline_service, session_service, artifact_service, metadata_service, discovery_service = _build()
        session = _start_session(pipeline_service, session_service)
        ids = ["artifact-1", "artifact-2", "artifact-3"]

        for artifact_id in ids:
            _register_artifact(artifact_service, session.session_id, artifact_id)
            metadata_service.tag(artifact_id, "reviewed")
            discovery_service.index(artifact_id)

        by_session_ids = [result.artifact_id for result in discovery_service.by_session(session.session_id)]
        by_tag_ids = [result.artifact_id for result in discovery_service.by_tag("reviewed")]
        by_type_ids = [result.artifact_id for result in discovery_service.by_type("log")]

        assert by_session_ids == ids
        assert by_tag_ids == ids
        assert by_type_ids == ids

    def test_search_never_mutates_artifacts(self):
        pipeline_service, session_service, artifact_service, metadata_service, discovery_service = _build()
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id, "artifact-1")
        metadata_service.tag(artifact.artifact_id, "reviewed")
        discovery_service.index(artifact.artifact_id)

        discovery_service.search(ExecutionArtifactQuery(session_id=session.session_id, tag="reviewed"))

        assert artifact_service.get(artifact.artifact_id) == artifact

    def test_rejects_query_with_no_criteria(self):
        with pytest.raises(Error):
            ExecutionArtifactQuery()

    def test_rejects_invalid_search_argument(self):
        *_rest, discovery_service = _build()

        with pytest.raises(Error):
            discovery_service.search("not-a-query")

    def test_index_rejects_unknown_artifact(self):
        *_rest, discovery_service = _build()

        with pytest.raises(Error):
            discovery_service.index("unknown-artifact")
