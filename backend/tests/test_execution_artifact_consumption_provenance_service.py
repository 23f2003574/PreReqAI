import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactAccessService,
    ExecutionArtifactConsumptionProvenance,
    ExecutionArtifactConsumptionProvenanceError as Error,
    ExecutionArtifactConsumptionProvenanceService,
    ExecutionArtifactConsumptionService,
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
    provenance_service = ExecutionArtifactConsumptionProvenanceService(consumption_service, version_service)
    return (
        pipeline_service,
        session_service,
        artifact_service,
        version_service,
        access_service,
        consumption_service,
        provenance_service,
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


def _prepare_active_consumption(
    pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
):
    session = _start_session(pipeline_service, session_service)
    artifact = _register_artifact(artifact_service, session.session_id)
    version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
    access_service.grant(artifact.artifact_id, "user-1", "READ")
    consumption = consumption_service.start("user-1", [artifact.artifact_id])
    return artifact, consumption


class TestExecutionArtifactConsumptionProvenanceService:
    def test_record_provenance(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, provenance_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )

        record = provenance_service.record(consumption.consumption_id, artifact.artifact_id)

        assert isinstance(record, ExecutionArtifactConsumptionProvenance)
        assert record.consumption_id == consumption.consumption_id
        assert record.artifact_id == artifact.artifact_id
        assert record.consumer == "user-1"

    def test_exact_version_capture(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, provenance_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        version_service.create(artifact.artifact_id, "/tmp/output-v2.log")

        record = provenance_service.record(consumption.consumption_id, artifact.artifact_id)

        assert record.version == 2

        version_service.create(artifact.artifact_id, "/tmp/output-v3.log")

        assert record.version == 2

    def test_history_lookup(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, provenance_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )

        first = provenance_service.record(consumption.consumption_id, artifact.artifact_id)
        second = provenance_service.record(consumption.consumption_id, artifact.artifact_id)

        history = provenance_service.history(consumption.consumption_id)

        assert [record.provenance_id for record in history] == [first.provenance_id, second.provenance_id]
        assert provenance_service.latest(consumption.consumption_id) == second

    def test_artifact_history(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, provenance_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        other_session = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2")
        other_artifact = _register_artifact(artifact_service, other_session.session_id, artifact_id="artifact-2")
        version_service.create(other_artifact.artifact_id, "/tmp/output-2-v1.log")
        access_service.grant(other_artifact.artifact_id, "user-2", "READ")
        other_consumption = consumption_service.start("user-2", [other_artifact.artifact_id])

        first = provenance_service.record(consumption.consumption_id, artifact.artifact_id)
        provenance_service.record(other_consumption.consumption_id, other_artifact.artifact_id)
        second = provenance_service.record(consumption.consumption_id, artifact.artifact_id)

        artifact_history = provenance_service.artifact_history(artifact.artifact_id)

        assert [record.provenance_id for record in artifact_history] == [first.provenance_id, second.provenance_id]

    def test_inactive_session_rejection(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, provenance_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        consumption_service.finish(consumption.consumption_id)

        with pytest.raises(Error):
            provenance_service.record(consumption.consumption_id, artifact.artifact_id)

        with pytest.raises(Error):
            provenance_service.record("unknown-consumption", artifact.artifact_id)

    def test_ordering(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, provenance_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )

        recorded = [
            provenance_service.record(consumption.consumption_id, artifact.artifact_id) for _ in range(5)
        ]

        history = provenance_service.history(consumption.consumption_id)

        assert [record.provenance_id for record in history] == [record.provenance_id for record in recorded]
        assert [record.recorded_at for record in history] == sorted(record.recorded_at for record in history)
