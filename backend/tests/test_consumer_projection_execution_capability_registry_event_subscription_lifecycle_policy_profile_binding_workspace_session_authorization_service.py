import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationService as AuthorizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPermission as Permission,
)


class TestWorkspaceSessionAuthorizationService:
    def test_grant_permission(self):
        service = AuthorizationService()

        granted = service.grant("operator", "START")

        assert isinstance(granted, Permission)
        assert granted.role == "operator"
        assert granted.operation == "START"
        assert granted in service.permissions("operator")

        with pytest.raises(Error):
            service.grant("operator", "not-a-real-operation")

    def test_revoke_permission(self):
        service = AuthorizationService()
        service.grant("operator", "START")

        service.revoke("operator", "START")

        assert service.permissions("operator") == ()

        result = service.authorize("session-1", "START", "operator")
        assert result.authorized is False

        # revoking a permission that was never granted is rejected
        with pytest.raises(Error):
            service.revoke("operator", "START")

    def test_successful_authorization(self):
        service = AuthorizationService()
        service.grant("operator", "START")

        result = service.authorize("session-1", "START", "operator")

        assert isinstance(result, Result)
        assert result.authorized is True
        assert result.reason is None

    def test_denied_authorization(self):
        service = AuthorizationService()
        service.grant("operator", "START")

        # operator holds START but not CANCEL: operation-specific permissions
        result = service.authorize("session-1", "CANCEL", "operator")

        assert result.authorized is False
        assert result.reason

        with pytest.raises(Error):
            service.authorize("session-1", "not-a-real-operation", "operator")

    def test_permission_lookup(self):
        service = AuthorizationService()
        service.grant("operator", "START")
        service.grant("operator", "CANCEL")
        service.grant("viewer", "START")

        operator_operations = {p.operation for p in service.permissions("operator")}
        assert operator_operations == {"START", "CANCEL"}

        viewer_operations = {p.operation for p in service.permissions("viewer")}
        assert viewer_operations == {"START"}

        with pytest.raises(Error):
            service.permissions("   ")

    def test_default_deny(self):
        service = AuthorizationService()

        # a role that has never been granted anything is denied every operation
        result = service.authorize("session-1", "START", "stranger")

        assert result.authorized is False
        assert "stranger" in result.reason
        assert service.permissions("stranger") == ()
