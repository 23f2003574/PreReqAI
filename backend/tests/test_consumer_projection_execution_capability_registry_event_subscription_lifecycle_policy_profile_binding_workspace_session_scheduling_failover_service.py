import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverPlan as Plan,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverService as FailoverService,
)


def _plan(plan_id, session_id, primary_worker, backup_workers):
    return Plan(
        plan_id=plan_id,
        session_id=session_id,
        primary_worker=primary_worker,
        backup_workers=backup_workers,
    )


class TestWorkspaceSessionSchedulingFailoverService:
    def test_successful_failover(self):
        service = FailoverService()
        service.register(_plan("plan-1", "session-1", "worker-a", ("worker-b", "worker-c")))

        result = service.failover("session-1")

        assert isinstance(result, Result)
        assert result.reassigned is True
        assert result.worker_id == "worker-b"
        assert service.available("worker-a") is False

    def test_worker_recovery(self):
        service = FailoverService()
        service.register(_plan("plan-1", "session-1", "worker-a", ("worker-b",)))
        service.failover("session-1")

        assert service.available("worker-a") is False

        service.recover("worker-a")

        assert service.available("worker-a") is True

    def test_unavailable_worker_detection(self):
        service = FailoverService()

        assert service.available("worker-x") is True

        service.register(_plan("plan-1", "session-1", "worker-x", ("worker-y",)))
        service.failover("session-1")

        assert service.available("worker-x") is False

    def test_backup_worker_selection(self):
        service = FailoverService()

        # mark worker-b unavailable via an unrelated session that primaries on it
        service.register(_plan("plan-x", "session-x", "worker-b", ("worker-z",)))
        service.failover("session-x")

        service.register(_plan("plan-1", "session-1", "worker-a", ("worker-b", "worker-c", "worker-d")))

        result = service.failover("session-1")

        # worker-b is skipped for being unavailable; worker-c is chosen next,
        # preserving plan order rather than jumping straight to worker-d
        assert result.worker_id == "worker-c"

    def test_status_lookup(self):
        service = FailoverService()
        service.register(_plan("plan-1", "session-1", "worker-a", ("worker-b",)))

        status = service.status("session-1")
        assert isinstance(status, Result)
        assert status.reassigned is False
        assert status.worker_id == "worker-a"

        service.failover("session-1")

        status = service.status("session-1")
        assert status.reassigned is True
        assert status.worker_id == "worker-b"

        with pytest.raises(Error):
            service.status("unknown-session")

    def test_missing_backup_rejection(self):
        with pytest.raises(Error):
            Plan(plan_id="plan-1", session_id="session-1", primary_worker="worker-a", backup_workers=())

        with pytest.raises(Error):
            Plan(plan_id="plan-1", session_id="session-1", primary_worker="worker-a", backup_workers=("worker-a",))

        with pytest.raises(Error):
            Plan(
                plan_id="plan-1",
                session_id="session-1",
                primary_worker="worker-a",
                backup_workers=("worker-b", "worker-b"),
            )

        service = FailoverService()
        service.register(_plan("plan-1", "session-1", "worker-a", ("worker-b",)))

        with pytest.raises(Error):
            service.register(_plan("plan-2", "session-1", "worker-c", ("worker-d",)))

        with pytest.raises(Error):
            service.failover("unknown-session")

        # exhaust the only backup: after this, session-1 is on worker-b
        service.failover("session-1")

        # worker-b is now the current worker; failing over again has no
        # backup left to try
        with pytest.raises(Error):
            service.failover("session-1")
