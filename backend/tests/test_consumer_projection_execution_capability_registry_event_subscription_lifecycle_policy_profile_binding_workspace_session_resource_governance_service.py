import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy as Policy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyService as PolicyService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourcePolicy as ResourcePolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceService as GovernanceService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceUsage as Usage,
)


def _session_policy(policy_id="policy-1"):
    return Policy(
        policy_id=policy_id,
        name="standard",
        max_runtime=3600,
        max_idle=300,
        allow_restore=True,
        enabled=True,
    )


def _resource_policy(policy_id="policy-1", cpu_limit=4, memory_limit=8, storage_limit=100):
    return ResourcePolicy(policy_id=policy_id, cpu_limit=cpu_limit, memory_limit=memory_limit, storage_limit=storage_limit)


def _governed_service(resource_policies, cpu_capacity=8, memory_capacity=16, storage_capacity=200, sessions=("session-1",), policy_id="policy-1"):
    policy_service = PolicyService()
    policy_service.register(_session_policy(policy_id))

    for session_id in sessions:
        policy_service.assign(session_id, policy_id)

    governance_service = GovernanceService(
        policy_service,
        resource_policies=resource_policies,
        cpu_capacity=cpu_capacity,
        memory_capacity=memory_capacity,
        storage_capacity=storage_capacity,
    )

    return policy_service, governance_service


class TestWorkspaceSessionResourceGovernanceService:
    def test_allocate_resources(self):
        _policy_service, governance_service = _governed_service([_resource_policy()])

        usage = governance_service.allocate("session-1")

        assert isinstance(usage, Usage)
        assert usage.cpu_used == 4
        assert usage.memory_used == 8
        assert usage.storage_used == 100

        with pytest.raises(Error):
            governance_service.allocate("session-1")

    def test_release_resources(self):
        _policy_service, governance_service = _governed_service([_resource_policy()])

        governance_service.allocate("session-1")
        governance_service.release("session-1")

        with pytest.raises(Error):
            governance_service.usage("session-1")

        # capacity freed by release() is available again
        usage = governance_service.allocate("session-1")
        assert usage.cpu_used == 4

        with pytest.raises(Error):
            governance_service.release("session-1-never-allocated")

    def test_usage_reporting(self):
        _policy_service, governance_service = _governed_service([_resource_policy()])

        with pytest.raises(Error):
            governance_service.usage("session-1")

        governance_service.allocate("session-1")
        usage = governance_service.usage("session-1")

        assert usage == Usage(session_id="session-1", cpu_used=4, memory_used=8, storage_used=100)
        assert governance_service.validate("session-1") is True

    def test_limit_enforcement(self):
        # this session's own policy alone exceeds total capacity
        _policy_service, governance_service = _governed_service(
            [_resource_policy(cpu_limit=100)],
            cpu_capacity=8,
        )

        with pytest.raises(Error):
            governance_service.allocate("session-1")

    def test_over_allocation_rejection(self):
        _policy_service, governance_service = _governed_service(
            [_resource_policy(policy_id="policy-1", cpu_limit=5)],
            cpu_capacity=8,
            sessions=("session-1", "session-2"),
        )

        first = governance_service.allocate("session-1")
        assert first.cpu_used == 5

        # session-2 individually fits its own policy, but 5 + 5 > 8 capacity
        with pytest.raises(Error):
            governance_service.allocate("session-2")

    def test_resource_cleanup(self):
        _policy_service, governance_service = _governed_service(
            [_resource_policy(policy_id="policy-1", cpu_limit=5)],
            cpu_capacity=8,
            sessions=("session-1", "session-2"),
        )

        governance_service.allocate("session-1")

        with pytest.raises(Error):
            governance_service.allocate("session-2")

        governance_service.release("session-1")

        # releasing session-1 frees enough capacity for session-2
        second = governance_service.allocate("session-2")
        assert second.cpu_used == 5

        with pytest.raises(Error):
            governance_service.usage("session-1")
