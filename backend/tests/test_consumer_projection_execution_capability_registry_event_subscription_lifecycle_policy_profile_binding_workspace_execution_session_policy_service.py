import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyAssignment as Assignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy as Policy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyService as PolicyService,
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


class TestWorkspaceExecutionSessionPolicyService:
    def test_register_policy(self):
        service = PolicyService()
        policy = _policy()

        registered = service.register(policy)

        assert registered == policy

        # a registered policy is reusable across any number of sessions
        service.assign("session-1", policy.policy_id)
        service.assign("session-2", policy.policy_id)

        assert service.policy("session-1") == policy
        assert service.policy("session-2") == policy

    def test_assign_unassign(self):
        service = PolicyService()
        policy = _policy()
        service.register(policy)

        assignment = service.assign("session-1", policy.policy_id)

        assert isinstance(assignment, Assignment)
        assert assignment.session_id == "session-1"
        assert assignment.policy_id == policy.policy_id
        assert service.policy("session-1") == policy

        service.unassign("session-1")

        with pytest.raises(Error):
            service.policy("session-1")

        # unassigning a session with no assignment is rejected
        with pytest.raises(Error):
            service.unassign("session-1")

    def test_effective_policy_lookup(self):
        service = PolicyService()
        first = _policy(policy_id="policy-1")
        second = _policy(policy_id="policy-2")
        service.register(first)
        service.register(second)

        service.assign("session-1", first.policy_id)

        # a session has at most one active policy: reassigning replaces it
        service.assign("session-1", second.policy_id)

        assert service.policy("session-1") == second

        with pytest.raises(Error):
            service.policy("unknown-session")

    def test_validation(self):
        service = PolicyService()
        policy = _policy()
        service.register(policy)
        service.assign("session-1", policy.policy_id)

        assert service.validate("session-1") is True

        # validation fails before a policy has ever been assigned
        with pytest.raises(Error):
            service.validate("session-2")

        with pytest.raises(Error):
            service.validate("   ")

    def test_duplicate_policy_rejection(self):
        service = PolicyService()
        service.register(_policy())

        with pytest.raises(Error):
            service.register(_policy())

    def test_disabled_policy_rejection(self):
        service = PolicyService()
        disabled = _policy(enabled=False)
        service.register(disabled)

        with pytest.raises(Error):
            service.assign("session-1", disabled.policy_id)

        with pytest.raises(Error):
            Policy(
                policy_id="policy-x",
                name="broken",
                max_runtime=0,
                max_idle=300,
                allow_restore=True,
                enabled=True,
            )
