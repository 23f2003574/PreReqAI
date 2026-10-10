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
    ExecutionArtifactConsumptionLease,
    ExecutionArtifactConsumptionLeaseError as Error,
    ExecutionArtifactConsumptionLeaseService,
    ExecutionArtifactConsumptionService,
    ExecutionArtifactRetrievalService,
    ExecutionArtifactService,
    ExecutionArtifactVersionService,
)


def _build(ttl=timedelta(minutes=15)):
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    version_service = ExecutionArtifactVersionService(artifact_service)
    access_service = ExecutionArtifactAccessService(artifact_service)
    retrieval_service = ExecutionArtifactRetrievalService(artifact_service, version_service, access_service)
    consumption_service = ExecutionArtifactConsumptionService(retrieval_service)
    lease_service = ExecutionArtifactConsumptionLeaseService(consumption_service, ttl=ttl)
    return (
        pipeline_service,
        session_service,
        artifact_service,
        version_service,
        access_service,
        consumption_service,
        lease_service,
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


class TestExecutionArtifactConsumptionLeaseService:
    def test_acquire_lease(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )

        lease = lease_service.acquire(consumption.consumption_id, artifact.artifact_id)

        assert isinstance(lease, ExecutionArtifactConsumptionLease)
        assert lease.consumption_id == consumption.consumption_id
        assert lease.artifact_id == artifact.artifact_id
        assert lease.status == "ACTIVE"

    def test_acquire_requires_active_consumption(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        consumption_service.finish(consumption.consumption_id)

        with pytest.raises(Error):
            lease_service.acquire(consumption.consumption_id, artifact.artifact_id)

    def test_acquire_requires_tracked_artifact(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service = (
            _build()
        )
        _artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )

        with pytest.raises(Error):
            lease_service.acquire(consumption.consumption_id, "untracked-artifact")

    def test_renew_lease(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        lease = lease_service.acquire(consumption.consumption_id, artifact.artifact_id)

        renewed = lease_service.renew(lease.lease_id)

        assert renewed.lease_id == lease.lease_id
        assert renewed.status == "ACTIVE"
        assert renewed.expires_at > lease.expires_at

    def test_release_lease(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        lease = lease_service.acquire(consumption.consumption_id, artifact.artifact_id)

        released = lease_service.release(lease.lease_id)

        assert released.status == "RELEASED"

        with pytest.raises(Error):
            lease_service.release(lease.lease_id)

        with pytest.raises(Error):
            lease_service.renew(lease.lease_id)

    def test_expiry_detection(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service = (
            _build(ttl=timedelta(seconds=-1))
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )

        lease = lease_service.acquire(consumption.consumption_id, artifact.artifact_id)

        assert lease_service.expired() == [lease]

        with pytest.raises(Error):
            lease_service.renew(lease.lease_id)

    def test_duplicate_lease_rejection(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        lease_service.acquire(consumption.consumption_id, artifact.artifact_id)

        with pytest.raises(Error):
            lease_service.acquire(consumption.consumption_id, artifact.artifact_id)

    def test_reacquire_after_release(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        first = lease_service.acquire(consumption.consumption_id, artifact.artifact_id)
        lease_service.release(first.lease_id)

        second = lease_service.acquire(consumption.consumption_id, artifact.artifact_id)

        assert second.lease_id != first.lease_id

    def test_cleanup(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, lease_service = (
            _build(ttl=timedelta(seconds=-1))
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        lease = lease_service.acquire(consumption.consumption_id, artifact.artifact_id)

        updated = lease_service.cleanup()

        assert len(updated) == 1
        assert updated[0].lease_id == lease.lease_id
        assert updated[0].status == "EXPIRED"
        assert lease_service.expired() == []

        reacquired = lease_service.acquire(consumption.consumption_id, artifact.artifact_id)
        assert reacquired.lease_id != lease.lease_id

    def test_rejects_unknown_lease(self):
        *_rest, lease_service = _build()

        with pytest.raises(Error):
            lease_service.renew("unknown-lease")

        with pytest.raises(Error):
            lease_service.release("unknown-lease")
