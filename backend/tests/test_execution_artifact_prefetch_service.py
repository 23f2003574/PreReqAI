import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactAccessService,
    ExecutionArtifactCacheService,
    ExecutionArtifactPrefetch,
    ExecutionArtifactPrefetchError as Error,
    ExecutionArtifactPrefetchService,
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
    cache_service = ExecutionArtifactCacheService()
    prefetch_service = ExecutionArtifactPrefetchService(retrieval_service, cache_service)
    return (
        pipeline_service,
        session_service,
        artifact_service,
        version_service,
        access_service,
        cache_service,
        prefetch_service,
    )


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


def _prepare_retrievable_artifact(pipeline_service, session_service, artifact_service, version_service, access_service):
    session = _start_session(pipeline_service, session_service)
    artifact = _register_artifact(artifact_service, session.session_id)
    version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
    access_service.grant(artifact.artifact_id, "user-1", "READ")
    return artifact


class TestExecutionArtifactPrefetchService:
    def test_schedule_prefetch(self):
        *_rest, prefetch_service = _build()

        prefetch = prefetch_service.schedule("artifact-1", "user-1")

        assert isinstance(prefetch, ExecutionArtifactPrefetch)
        assert prefetch.artifact_id == "artifact-1"
        assert prefetch.consumer == "user-1"
        assert prefetch.status == "PENDING"

    def test_execute_prefetch(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, cache_service, prefetch_service = (
            _build()
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )
        prefetch = prefetch_service.schedule(artifact.artifact_id, "user-1")

        executed = prefetch_service.execute(prefetch.prefetch_id)

        assert executed.status == "SUCCEEDED"
        assert cache_service.get(artifact.artifact_id, "user-1") is not None
        assert prefetch_service.status(prefetch.prefetch_id) == executed

        with pytest.raises(Error):
            prefetch_service.execute(prefetch.prefetch_id)

    def test_cache_hit_skip(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, cache_service, prefetch_service = (
            _build()
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )
        cache_service.put(artifact.artifact_id, 1, "user-1")
        prefetch = prefetch_service.schedule(artifact.artifact_id, "user-1")

        executed = prefetch_service.execute(prefetch.prefetch_id)

        assert executed.status == "SKIPPED"

    def test_cancel(self):
        *_rest, prefetch_service = _build()
        prefetch = prefetch_service.schedule("artifact-1", "user-1")

        cancelled = prefetch_service.cancel(prefetch.prefetch_id)

        assert cancelled.status == "CANCELLED"

        with pytest.raises(Error):
            prefetch_service.cancel(prefetch.prefetch_id)

        with pytest.raises(Error):
            prefetch_service.execute(prefetch.prefetch_id)

    def test_pending_lookup(self):
        *_rest, prefetch_service = _build()
        first = prefetch_service.schedule("artifact-1", "user-1")
        second = prefetch_service.schedule("artifact-2", "user-1")
        prefetch_service.schedule("artifact-3", "user-2")
        prefetch_service.cancel(second.prefetch_id)

        pending = prefetch_service.pending("user-1")

        assert [prefetch.prefetch_id for prefetch in pending] == [first.prefetch_id]

    def test_failure_status(self):
        pipeline_service, session_service, artifact_service, version_service, _access_service, _cache_service, prefetch_service = (
            _build()
        )
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
        prefetch = prefetch_service.schedule(artifact.artifact_id, "user-1")

        executed = prefetch_service.execute(prefetch.prefetch_id)

        assert executed.status == "FAILED"
        assert prefetch_service.status(prefetch.prefetch_id).status == "FAILED"

    def test_rejects_unknown_prefetch(self):
        *_rest, prefetch_service = _build()

        with pytest.raises(Error):
            prefetch_service.execute("unknown-prefetch")

        with pytest.raises(Error):
            prefetch_service.cancel("unknown-prefetch")

        with pytest.raises(Error):
            prefetch_service.status("unknown-prefetch")
