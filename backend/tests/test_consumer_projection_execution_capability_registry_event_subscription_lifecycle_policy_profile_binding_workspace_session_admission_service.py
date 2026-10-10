from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy as Policy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyService as PolicyService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionRequest as Request,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionService as AdmissionService,
)


def _policy(policy_id="policy-1", enabled=True):
    return Policy(
        policy_id=policy_id,
        name="standard",
        max_runtime=3600,
        max_idle=300,
        allow_restore=True,
        enabled=enabled,
    )


def _request(session_id="session-1", policy_id="policy-1"):
    return Request(session_id=session_id, policy_id=policy_id, requested_at=datetime.now(timezone.utc))


def _governed_policy_service(policy_id="policy-1", enabled=True, sessions=("session-1",)):
    policy_service = PolicyService()
    policy_service.register(_policy(policy_id=policy_id, enabled=enabled))

    for session_id in sessions:
        policy_service.assign(session_id, policy_id)

    return policy_service


class TestWorkspaceSessionAdmissionService:
    def test_successful_admission(self):
        policy_service = _governed_policy_service()
        admission_service = AdmissionService(policy_service, capacity=2)

        result = admission_service.admit(_request())

        assert isinstance(result, Result)
        assert result.accepted is True
        assert result.reason is None
        assert admission_service.can_start("session-1") is True
        assert "session-1" in [r.session_id for r in admission_service.pending()]

    def test_policy_rejection(self):
        policy_service = PolicyService()
        admission_service = AdmissionService(policy_service, capacity=2)

        # session-1 has no policy assigned at all
        result = admission_service.admit(_request())

        assert result.accepted is False
        assert result.reason

        # session governed by a different policy than requested
        policy_service.register(_policy(policy_id="policy-1"))
        policy_service.register(_policy(policy_id="policy-2"))
        policy_service.assign("session-2", "policy-2")

        mismatched = admission_service.admit(_request(session_id="session-2", policy_id="policy-1"))

        assert mismatched.accepted is False
        assert mismatched.reason

    def test_capacity_rejection(self):
        policy_service = _governed_policy_service(sessions=("session-1", "session-2", "session-3"))
        admission_service = AdmissionService(policy_service, capacity=2)

        first = admission_service.admit(_request(session_id="session-1"))
        second = admission_service.admit(_request(session_id="session-2"))
        third = admission_service.admit(_request(session_id="session-3"))

        assert first.accepted is True
        assert second.accepted is True
        assert third.accepted is False
        assert "capacity" in third.reason.lower()

        # freeing a slot allows a subsequent request through
        admission_service.reject("session-1", "no longer needed")
        retry = admission_service.admit(_request(session_id="session-3"))

        assert retry.accepted is True

    def test_duplicate_session_rejection(self):
        policy_service = _governed_policy_service()
        admission_service = AdmissionService(policy_service, capacity=5)

        first = admission_service.admit(_request())
        second = admission_service.admit(_request())

        assert first.accepted is True
        assert second.accepted is False
        assert second.reason

    def test_pending_admissions(self):
        policy_service = _governed_policy_service(sessions=("session-1", "session-2"))
        admission_service = AdmissionService(policy_service, capacity=5)

        admission_service.admit(_request(session_id="session-1"))
        admission_service.admit(_request(session_id="session-2"))

        pending_ids = {r.session_id for r in admission_service.pending()}
        assert pending_ids == {"session-1", "session-2"}

        admission_service.reject("session-1", "cancelled by operator")

        pending_ids = {r.session_id for r in admission_service.pending()}
        assert pending_ids == {"session-2"}

    def test_can_start_evaluation(self):
        policy_service = _governed_policy_service()
        admission_service = AdmissionService(policy_service, capacity=1)

        with pytest.raises(Error):
            admission_service.can_start("session-1")

        admission_service.admit(_request())
        assert admission_service.can_start("session-1") is True

        admission_service.reject("session-1", "operator override")
        assert admission_service.can_start("session-1") is False

        with pytest.raises(Error):
            admission_service.can_start("   ")
