import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactAccessService,
    ExecutionArtifactConsumptionError as Error,
    ExecutionArtifactConsumptionService,
    ExecutionArtifactConsumptionSession,
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
    consumption_service = ExecutionArtifactConsumptionService(retrieval_service)
    return (
        pipeline_service,
        session_service,
        artifact_service,
        version_service,
        access_service,
        consumption_service,
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


def _prepare_retrievable_artifact(
    pipeline_service, session_service, artifact_service, version_service, access_service, artifact_id="artifact-1"
):
    session = _start_session(pipeline_service, session_service, pipeline_id=f"pipeline-{artifact_id}")
    artifact = _register_artifact(artifact_service, session.session_id, artifact_id=artifact_id)
    version_service.create(artifact.artifact_id, f"/tmp/{artifact_id}-v1.log")
    access_service.grant(artifact.artifact_id, "user-1", "READ")
    return artifact


class TestExecutionArtifactConsumptionService:
    def test_start_session(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service = (
            _build()
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )

        consumption = consumption_service.start("user-1", [artifact.artifact_id])

        assert isinstance(consumption, ExecutionArtifactConsumptionSession)
        assert consumption.consumer == "user-1"
        assert consumption.artifact_ids == (artifact.artifact_id,)
        assert consumption.status == "ACTIVE"

    def test_add_and_remove_artifact(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service = (
            _build()
        )
        first = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-1"
        )
        second = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-2"
        )
        consumption = consumption_service.start("user-1", [first.artifact_id])

        added = consumption_service.add(consumption.consumption_id, second.artifact_id)
        assert added.artifact_ids == (first.artifact_id, second.artifact_id)

        removed = consumption_service.remove(consumption.consumption_id, first.artifact_id)
        assert removed.artifact_ids == (second.artifact_id,)

    def test_duplicate_rejection(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service = (
            _build()
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )
        consumption = consumption_service.start("user-1", [artifact.artifact_id])

        with pytest.raises(Error):
            consumption_service.add(consumption.consumption_id, artifact.artifact_id)

        with pytest.raises(Error):
            consumption_service.start("user-1", [artifact.artifact_id, artifact.artifact_id])

    def test_finish_session(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service = (
            _build()
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )
        consumption = consumption_service.start("user-1", [artifact.artifact_id])

        finished = consumption_service.finish(consumption.consumption_id)
        assert finished.status == "FINISHED"

        with pytest.raises(Error):
            consumption_service.finish(consumption.consumption_id)

        with pytest.raises(Error):
            consumption_service.add(consumption.consumption_id, artifact.artifact_id)

        with pytest.raises(Error):
            consumption_service.remove(consumption.consumption_id, artifact.artifact_id)

    def test_active_lookup(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service = (
            _build()
        )
        first = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-1"
        )
        second_consumption = consumption_service.start("user-1", [])
        first_consumption = consumption_service.start("user-1", [first.artifact_id])
        consumption_service.finish(second_consumption.consumption_id)

        active = consumption_service.active("user-1")

        assert [session.consumption_id for session in active] == [first_consumption.consumption_id]
        assert consumption_service.active("user-2") == []

    def test_unauthorized_artifact(self):
        pipeline_service, session_service, artifact_service, version_service, _access_service, consumption_service = (
            _build()
        )
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v1.log")

        with pytest.raises(Error):
            consumption_service.start("user-1", [artifact.artifact_id])

        consumption = consumption_service.start("user-1", [])

        with pytest.raises(Error):
            consumption_service.add(consumption.consumption_id, artifact.artifact_id)

    def test_rejects_unknown_session(self):
        *_rest, consumption_service = _build()

        with pytest.raises(Error):
            consumption_service.add("unknown-consumption", "artifact-1")

        with pytest.raises(Error):
            consumption_service.remove("unknown-consumption", "artifact-1")

        with pytest.raises(Error):
            consumption_service.finish("unknown-consumption")
