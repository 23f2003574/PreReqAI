from datetime import (
    timedelta,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactAccessService,
    ExecutionArtifactConsumptionHealth,
    ExecutionArtifactConsumptionHealthError as Error,
    ExecutionArtifactConsumptionHealthService,
    ExecutionArtifactConsumptionLeaseService,
    ExecutionArtifactConsumptionService,
    ExecutionArtifactConsumptionSnapshotService,
    ExecutionArtifactConsumptionValidationService,
    ExecutionArtifactRetrievalService,
    ExecutionArtifactService,
    ExecutionArtifactVersionService,
)


def _build(stale_after=timedelta(minutes=30), lease_ttl=timedelta(minutes=15)):
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
    lease_service = ExecutionArtifactConsumptionLeaseService(consumption_service, ttl=lease_ttl)
    health_service = ExecutionArtifactConsumptionHealthService(
        consumption_service, lease_service, validation_service, stale_after=stale_after
    )
    return (
        pipeline_service,
        session_service,
        artifact_service,
        version_service,
        access_service,
        consumption_service,
        lease_service,
        validation_service,
        health_service,
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
    pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service,
    consumer="user-1",
):
    session = _start_session(pipeline_service, session_service, owner=consumer)
    artifact = _register_artifact(artifact_service, session.session_id)
    version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
    access_service.grant(artifact.artifact_id, consumer, "READ")
    consumption = consumption_service.start(consumer, [artifact.artifact_id])
    return artifact, consumption


class TestExecutionArtifactConsumptionHealthService:
    def test_healthy_session(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service, _validation_service, health_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        lease_service.acquire(consumption.consumption_id, artifact.artifact_id)
        health_service.refresh(consumption.consumption_id)

        health = health_service.check(consumption.consumption_id)

        assert isinstance(health, ExecutionArtifactConsumptionHealth)
        assert health.status == "HEALTHY"
        assert health.invalid_artifacts == ()

    def test_stale_session(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service, _validation_service, health_service = (
            _build(stale_after=timedelta(seconds=-1))
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        lease_service.acquire(consumption.consumption_id, artifact.artifact_id)
        health_service.refresh(consumption.consumption_id)

        health = health_service.check(consumption.consumption_id)

        assert health.status == "STALE"

    def test_invalid_artifact(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service, _validation_service, health_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        health_service.refresh(consumption.consumption_id)
        access_service.revoke(artifact.artifact_id, "user-1", "READ")

        health = health_service.check(consumption.consumption_id)

        assert health.status == "UNHEALTHY"
        assert health.invalid_artifacts == (artifact.artifact_id,)

    def test_expired_lease(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service, _validation_service, health_service = (
            _build(lease_ttl=timedelta(seconds=-1))
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        lease_service.acquire(consumption.consumption_id, artifact.artifact_id)
        health_service.refresh(consumption.consumption_id)

        health = health_service.check(consumption.consumption_id)

        assert health.status == "UNHEALTHY"
        assert health.invalid_artifacts == (artifact.artifact_id,)

    def test_consumer_health_lookup(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service, _validation_service, health_service = (
            _build()
        )
        healthy_artifact, healthy_consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        session2 = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-1")
        unhealthy_artifact = _register_artifact(artifact_service, session2.session_id, artifact_id="artifact-2")
        version_service.create(unhealthy_artifact.artifact_id, "/tmp/output-2-v1.log")
        access_service.grant(unhealthy_artifact.artifact_id, "user-1", "READ")
        unhealthy_consumption = consumption_service.start("user-1", [unhealthy_artifact.artifact_id])
        access_service.revoke(unhealthy_artifact.artifact_id, "user-1", "READ")

        healthy_results = health_service.healthy("user-1")

        assert [health.consumption_id for health in healthy_results] == [healthy_consumption.consumption_id]
        assert health_service.healthy("user-2") == []

    def test_refresh(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service, _validation_service, health_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )

        before = health_service.check(consumption.consumption_id)
        assert before.status == "HEALTHY"
        assert before.last_activity == consumption.started_at

        refreshed = health_service.refresh(consumption.consumption_id)

        assert refreshed.status == "HEALTHY"
        assert refreshed.last_activity > before.last_activity
        assert health_service.stale() == []

    def test_rejects_unknown_consumption(self):
        *_rest, health_service = _build()

        with pytest.raises(Error):
            health_service.check("unknown-consumption")

        with pytest.raises(Error):
            health_service.refresh("unknown-consumption")
