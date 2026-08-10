import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactAccessService,
    ExecutionArtifactConsumptionService,
    ExecutionArtifactConsumptionSnapshotService,
    ExecutionArtifactConsumptionValidation,
    ExecutionArtifactConsumptionValidationError as Error,
    ExecutionArtifactConsumptionValidationService,
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
    snapshot_service = ExecutionArtifactConsumptionSnapshotService(consumption_service, version_service)
    validation_service = ExecutionArtifactConsumptionValidationService(
        consumption_service, artifact_service, access_service, version_service, snapshot_service
    )
    return (
        pipeline_service,
        session_service,
        artifact_service,
        version_service,
        access_service,
        consumption_service,
        snapshot_service,
        validation_service,
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


class TestExecutionArtifactConsumptionValidationService:
    def test_valid_consumption(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, _snapshot_service, validation_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )

        results = validation_service.validate(consumption.consumption_id)

        assert len(results) == 1
        assert isinstance(results[0], ExecutionArtifactConsumptionValidation)
        assert results[0].artifact_id == artifact.artifact_id
        assert results[0].valid is True
        assert validation_service.invalid(consumption.consumption_id) == []

    def test_missing_artifact(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, _snapshot_service, validation_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        artifact_service.remove(artifact.artifact_id)

        results = validation_service.validate(consumption.consumption_id)

        assert results[0].valid is False
        assert "does not exist" in results[0].reason

    def test_access_denial(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, _snapshot_service, validation_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        access_service.revoke(artifact.artifact_id, "user-1", "READ")

        results = validation_service.validate(consumption.consumption_id)

        assert results[0].valid is False
        assert "access" in results[0].reason.lower()

    def test_version_mismatch(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service, validation_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        snapshot_service.create(consumption.consumption_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v2.log")

        results = validation_service.validate(consumption.consumption_id)

        assert results[0].valid is False
        assert "version" in results[0].reason.lower()

    def test_invalid_artifact_lookup(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, _snapshot_service, validation_service = (
            _build()
        )
        _artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )

        with pytest.raises(Error):
            validation_service.validate_artifact(consumption.consumption_id, "untracked-artifact")

        with pytest.raises(Error):
            validation_service.validate_artifact("unknown-consumption", "artifact-1")

    def test_validation_report(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, _snapshot_service, validation_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        access_service.revoke(artifact.artifact_id, "user-1", "READ")

        report = validation_service.report(consumption.consumption_id)

        assert report["consumption_id"] == consumption.consumption_id
        assert report["total"] == 1
        assert report["valid_count"] == 0
        assert report["invalid_count"] == 1
        assert len(report["violations"]) == 1
        assert report["violations"][0].artifact_id == artifact.artifact_id
