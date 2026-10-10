import time

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyException as PolicyException,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionService as ExceptionService,
)


class TestWorkspaceSessionPolicyExceptionService:
    def test_request_exception(self):
        service = ExceptionService(scope="MAX_RUNTIME", duration_seconds=3600)

        exception = service.request("session-1", "policy-1")

        assert isinstance(exception, PolicyException)
        assert exception.session_id == "session-1"
        assert exception.policy_id == "policy-1"
        assert exception.scope == "MAX_RUNTIME"

        # requesting an exception never touches the base policy: nothing to assert
        # about policy-1 itself, since this service has no notion of it beyond the ID
        with pytest.raises(Error):
            service.request("   ", "policy-1")

    def test_approve_revoke(self):
        service = ExceptionService(scope="MAX_RUNTIME", duration_seconds=3600)
        exception = service.request("session-1", "policy-1")

        approved = service.approve(exception.exception_id)
        assert isinstance(approved, Result)
        assert approved.approved is True
        assert approved.reason is None

        assert exception in service.active("session-1")

        # approving twice is rejected
        with pytest.raises(Error):
            service.approve(exception.exception_id)

        revoked = service.revoke(exception.exception_id)
        assert revoked.approved is False
        assert revoked.reason

        assert exception not in service.active("session-1")

        with pytest.raises(Error):
            service.approve(exception.exception_id)

    def test_expiration_handling(self):
        service = ExceptionService(scope="MAX_RUNTIME", duration_seconds=0.05)
        exception = service.request("session-1", "policy-1")
        service.approve(exception.exception_id)

        assert exception in service.active("session-1")

        time.sleep(0.1)

        # the exception has aged out even though it was never revoked
        assert exception not in service.active("session-1")

    def test_active_exception_lookup(self):
        service = ExceptionService(scope="ALLOW_RESTORE", duration_seconds=3600)

        first = service.request("session-1", "policy-1")
        second = service.request("session-1", "policy-2")
        service.approve(first.exception_id)

        active_ids = {exception.exception_id for exception in service.active("session-1")}
        assert active_ids == {first.exception_id}

        service.approve(second.exception_id)
        active_ids = {exception.exception_id for exception in service.active("session-1")}
        assert active_ids == {first.exception_id, second.exception_id}

        assert service.active("session-2") == ()

        with pytest.raises(Error):
            service.active("   ")

    def test_validation(self):
        service = ExceptionService(scope="MAX_IDLE", duration_seconds=3600)

        no_exception = service.validate("session-1")
        assert no_exception.approved is False
        assert no_exception.reason

        exception = service.request("session-1", "policy-1")
        pending = service.validate("session-1")
        assert pending.approved is False

        service.approve(exception.exception_id)
        approved = service.validate("session-1")
        assert approved.approved is True
        assert approved.reason is None

    def test_expired_exception_rejection(self):
        service = ExceptionService(scope="MAX_IDLE", duration_seconds=0.05)
        exception = service.request("session-1", "policy-1")
        service.approve(exception.exception_id)

        time.sleep(0.1)

        result = service.validate("session-1")
        assert result.approved is False
        assert "expired" in result.reason.lower()
