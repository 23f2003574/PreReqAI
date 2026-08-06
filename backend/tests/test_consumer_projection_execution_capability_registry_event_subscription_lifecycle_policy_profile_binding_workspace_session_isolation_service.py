import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationPolicy as IsolationPolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationService as IsolationService,
)


def _strict_policy(shared_resources=()):
    return IsolationPolicy(policy_id="policy-1", isolation_level="STRICT", shared_resources=shared_resources)


def _shared_policy(shared_resources=()):
    return IsolationPolicy(policy_id="policy-1", isolation_level="SHARED", shared_resources=shared_resources)


class TestWorkspaceSessionIsolationService:
    def test_isolated_session(self):
        service = IsolationService(_strict_policy())

        result = service.validate("session-1")

        assert isinstance(result, Result)
        assert result.isolated is True
        assert result.violations == ()

        service.grant("session-1", "resource-1")

        # a lone session's own private grant is never a violation
        result = service.validate("session-1")
        assert result.isolated is True

    def test_shared_resource_access(self):
        service = IsolationService(_strict_policy(shared_resources=("shared-1",)))

        service.grant("session-1", "shared-1")
        service.grant("session-2", "shared-1")

        assert "shared-1" in service.accessible("session-1")
        assert "shared-1" in service.accessible("session-2")

        # a resource declared shared never causes a violation, even under STRICT
        assert service.validate("session-1").isolated is True
        assert service.validate("session-2").isolated is True

    def test_unauthorized_access_denial(self):
        service = IsolationService(_strict_policy())

        service.grant("session-1", "private-1")

        with pytest.raises(Error):
            service.grant("session-2", "private-1")

        assert "private-1" not in service.accessible("session-2")

    def test_grant_revoke_access(self):
        service = IsolationService(_strict_policy())

        service.grant("session-1", "resource-1")
        assert "resource-1" in service.accessible("session-1")

        service.revoke("session-1", "resource-1")
        assert "resource-1" not in service.accessible("session-1")

        with pytest.raises(Error):
            service.revoke("session-1", "resource-1")

    def test_accessible_resource_lookup(self):
        service = IsolationService(_strict_policy(shared_resources=("shared-1",)))

        service.grant("session-1", "private-1")

        assert set(service.accessible("session-1")) == {"shared-1", "private-1"}
        assert set(service.accessible("session-2")) == {"shared-1"}

        with pytest.raises(Error):
            service.accessible("   ")

    def test_isolation_validation(self):
        # under a SHARED policy, grant() places no exclusivity restriction at all
        service = IsolationService(_shared_policy())

        service.grant("session-1", "resource-1")
        service.grant("session-2", "resource-1")

        assert service.validate("session-1").isolated is True
        assert service.validate("session-2").isolated is True

        with pytest.raises(Error):
            service.validate("   ")
