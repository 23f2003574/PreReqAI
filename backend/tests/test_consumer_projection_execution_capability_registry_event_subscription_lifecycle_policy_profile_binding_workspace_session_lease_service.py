import time

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLease as Lease,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseService as LeaseService,
)


def _build(lease_duration_seconds=60.0):
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    lease_service = LeaseService(session_service, lease_duration_seconds=lease_duration_seconds)
    return pipeline_service, session_service, lease_service


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


class TestWorkspaceSessionLeaseService:
    def test_acquire_lease(self):
        pipeline_service, session_service, lease_service = _build()
        session = _start_session(pipeline_service, session_service)

        lease = lease_service.acquire(session.session_id, "worker-1")

        assert isinstance(lease, Lease)
        assert lease.session_id == session.session_id
        assert lease.holder_id == "worker-1"
        assert lease.expires_at > lease.acquired_at

    def test_renew_lease(self):
        pipeline_service, session_service, lease_service = _build()
        session = _start_session(pipeline_service, session_service)

        lease = lease_service.acquire(session.session_id, "worker-1")
        renewed = lease_service.renew(lease.lease_id)

        assert isinstance(renewed, Lease)
        assert renewed.lease_id == lease.lease_id
        assert renewed.expires_at >= lease.expires_at

    def test_release_lease(self):
        pipeline_service, session_service, lease_service = _build()
        session = _start_session(pipeline_service, session_service)

        lease = lease_service.acquire(session.session_id, "worker-1")
        result = lease_service.release(lease.lease_id)

        assert isinstance(result, Result)
        assert result.lease_id == lease.lease_id
        assert result.active is False

        assert lease_service.owner(session.session_id) is None

        # freed immediately: a new lease can now be acquired
        new_lease = lease_service.acquire(session.session_id, "worker-2")
        assert new_lease.lease_id != lease.lease_id

    def test_expire_lease(self):
        pipeline_service, session_service, lease_service = _build(lease_duration_seconds=0.05)
        session = _start_session(pipeline_service, session_service)

        lease = lease_service.acquire(session.session_id, "worker-1")

        time.sleep(0.1)

        assert lease_service.owner(session.session_id) is None

        expired = lease_service.expired()

        assert len(expired) == 1
        assert expired[0].lease_id == lease.lease_id
        assert expired[0].active is False

        with pytest.raises(Error):
            lease_service.renew(lease.lease_id)

        # freed automatically: a new lease can now be acquired
        new_lease = lease_service.acquire(session.session_id, "worker-2")
        assert new_lease.lease_id != lease.lease_id

    def test_duplicate_lease_rejection(self):
        pipeline_service, session_service, lease_service = _build()
        session = _start_session(pipeline_service, session_service)

        lease_service.acquire(session.session_id, "worker-1")

        with pytest.raises(Error):
            lease_service.acquire(session.session_id, "worker-2")

    def test_session_owner_lookup(self):
        pipeline_service, session_service, lease_service = _build()
        session = _start_session(pipeline_service, session_service)

        assert lease_service.owner(session.session_id) is None

        lease = lease_service.acquire(session.session_id, "worker-1")

        owner = lease_service.owner(session.session_id)
        assert isinstance(owner, Lease)
        assert owner.lease_id == lease.lease_id
        assert owner.holder_id == "worker-1"

    def test_blank_and_unknown_id_rejection(self):
        pipeline_service, session_service, lease_service = _build()
        session = _start_session(pipeline_service, session_service)

        with pytest.raises(Error):
            lease_service.acquire("   ", "worker-1")

        with pytest.raises(Error):
            lease_service.acquire(session.session_id, "   ")

        with pytest.raises(Error):
            lease_service.acquire("unknown-session", "worker-1")

        with pytest.raises(Error):
            lease_service.renew("   ")

        with pytest.raises(Error):
            lease_service.renew("unknown-lease")

        with pytest.raises(Error):
            lease_service.release("   ")

        with pytest.raises(Error):
            lease_service.release("unknown-lease")

        with pytest.raises(Error):
            lease_service.owner("   ")
