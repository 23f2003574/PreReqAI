import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority as Priority,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityService as PriorityService,
)


def _priority(session_id, priority, aging_enabled=False):
    return Priority(session_id=session_id, priority=priority, aging_enabled=aging_enabled)


class TestWorkspaceSessionPriorityService:
    def test_priority_ordering(self):
        service = PriorityService()

        service.assign("session-a", _priority("session-a", 5))
        service.assign("session-b", _priority("session-b", 10))

        upcoming = service.next()

        assert isinstance(upcoming, Priority)
        assert upcoming.session_id == "session-b"

    def test_fifo_ordering(self):
        service = PriorityService()

        service.assign("session-a", _priority("session-a", 5))
        service.assign("session-b", _priority("session-b", 5))

        upcoming = service.next()

        assert upcoming.session_id == "session-a"

    def test_aging_behavior(self):
        service = PriorityService(aging_increment=1.0)

        service.assign("session-a", _priority("session-a", 1, aging_enabled=True))
        service.assign("session-b", _priority("session-b", 5, aging_enabled=False))

        assert service.next().session_id == "session-b"

        for _ in range(5):
            service.update("session-a")

        assert service.effective("session-a").effective_priority == 6.0
        assert service.next().session_id == "session-a"

    def test_rebalance(self):
        service = PriorityService(aging_increment=1.0)

        service.assign("session-a", _priority("session-a", 1, aging_enabled=True))
        service.assign("session-b", _priority("session-b", 2, aging_enabled=False))
        service.assign("session-c", _priority("session-c", 3, aging_enabled=True))

        results = service.rebalance()

        assert len(results) == 3
        assert all(isinstance(result, Result) for result in results)

        assert service.effective("session-a").effective_priority == 2.0
        assert service.effective("session-b").effective_priority == 2.0
        assert service.effective("session-c").effective_priority == 4.0

        # session-c leads with 4.0; session-a and session-b tie at 2.0 and
        # break FIFO, with session-a assigned first, so rebalance()
        # reports them in that order: c, then a, then b
        assert [result.effective_priority for result in results] == [4.0, 2.0, 2.0]
        assert [result.execution_order for result in results] == [0, 1, 2]

    def test_effective_priority_lookup(self):
        service = PriorityService()

        service.assign("session-a", _priority("session-a", 7))

        result = service.effective("session-a")

        assert isinstance(result, Result)
        assert result.execution_order == 0
        assert result.effective_priority == 7.0

        with pytest.raises(Error):
            service.effective("unknown-session")

    def test_invalid_priority_rejection(self):
        with pytest.raises(Error):
            Priority(session_id="   ", priority=1, aging_enabled=True)

        with pytest.raises(Error):
            Priority(session_id="session-a", priority=-1, aging_enabled=True)

        with pytest.raises(Error):
            Priority(session_id="session-a", priority=1.5, aging_enabled=True)

        with pytest.raises(Error):
            Priority(session_id="session-a", priority=1, aging_enabled="yes")

        service = PriorityService()

        with pytest.raises(Error):
            service.assign("session-a", "not-a-priority")

        with pytest.raises(Error):
            service.assign("session-b", _priority("session-a", 1))

        with pytest.raises(Error):
            service.update("unknown-session")

        with pytest.raises(Error):
            service.effective("   ")

        with pytest.raises(Error):
            service.update("   ")

        with pytest.raises(Error):
            PriorityService(aging_increment=0)
