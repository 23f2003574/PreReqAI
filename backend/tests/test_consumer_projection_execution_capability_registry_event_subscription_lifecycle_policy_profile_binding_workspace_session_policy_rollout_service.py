import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy as Policy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyService as PolicyService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRollout as Rollout,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutService as RolloutService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionService as VersionService,
)


def _configuration_provider(policy_id):
    return {"max_runtime": 3600}


def _policy_service_with(policy_id="policy-1", sessions=("session-1",)):
    policy_service = PolicyService()
    policy_service.register(
        Policy(policy_id=policy_id, name="standard", max_runtime=3600, max_idle=300, allow_restore=True, enabled=True)
    )

    for session_id in sessions:
        policy_service.assign(session_id, policy_id)

    return policy_service


def _versioned(policy_id="policy-1", sessions=("session-1",), publishes=2):
    policy_service = _policy_service_with(policy_id, sessions)
    version_service = VersionService(policy_service, _configuration_provider)

    for _ in range(publishes):
        version_service.publish(policy_id)

    return policy_service, version_service


class TestWorkspaceSessionPolicyRolloutService:
    def test_start_rollout(self):
        _policy_service, version_service = _versioned(publishes=2)
        rollout_service = RolloutService(version_service, strategy="FULL", percentage=100)

        rollout = rollout_service.start("policy-1", 2)

        assert isinstance(rollout, Rollout)
        assert rollout.policy_id == "policy-1"
        assert rollout.target_version == 2
        assert rollout_service.status(rollout.rollout_id) == "RUNNING"

        with pytest.raises(Error):
            rollout_service.start("   ", 2)

    def test_stop_rollout(self):
        # only version 1 is published; the rollout targets a version ahead of it
        _policy_service, version_service = _versioned(publishes=1)
        rollout_service = RolloutService(version_service, strategy="FULL", percentage=100)
        rollout = rollout_service.start("policy-1", 2)

        rollout_service.stop(rollout.rollout_id)
        assert rollout_service.status(rollout.rollout_id) == "STOPPED"

        with pytest.raises(Error):
            rollout_service.stop(rollout.rollout_id)

        # a new session resolved after the rollout stopped is unaffected by it:
        # it falls back to the base latest version instead of the rollout's target
        result = rollout_service.resolve("session-1")
        assert result.applied is False
        assert result.assigned_version == 1

    def test_version_resolution(self):
        _policy_service, version_service = _versioned(publishes=2)
        rollout_service = RolloutService(version_service, strategy="FULL", percentage=100)
        rollout_service.start("policy-1", 2)

        result = rollout_service.resolve("session-1")

        assert isinstance(result, Result)
        assert result.applied is True
        assert result.assigned_version == 2

        # existing sessions unchanged: a later call keeps returning the same outcome
        assert rollout_service.resolve("session-1") == result

    def test_rollout_progress(self):
        _policy_service, version_service = _versioned(sessions=("session-1", "session-2"), publishes=2)
        rollout_service = RolloutService(version_service, strategy="FULL", percentage=100)
        rollout = rollout_service.start("policy-1", 2)

        rollout_service.resolve("session-1")
        rollout_service.resolve("session-2")

        progress = rollout_service.progress(rollout.rollout_id)
        assert progress == {"total": 2, "applied": 2}

        with pytest.raises(Error):
            rollout_service.progress("unknown-rollout")

    def test_percentage_rollout(self):
        sessions = tuple(f"session-{i}" for i in range(200))
        _policy_service, version_service = _versioned(sessions=sessions, publishes=2)
        rollout_service = RolloutService(version_service, strategy="PERCENTAGE", percentage=50)
        rollout = rollout_service.start("policy-1", 2)

        for session_id in sessions:
            rollout_service.resolve(session_id)

        progress = rollout_service.progress(rollout.rollout_id)

        # a 50% rollout over 200 sessions should apply to some but not all
        assert progress["total"] == 200
        assert 0 < progress["applied"] < 200

        # resolution for a given session_id is deterministic and repeatable
        assert rollout_service.resolve(sessions[0]) == rollout_service.resolve(sessions[0])

    def test_duplicate_rollout_rejection(self):
        _policy_service, version_service = _versioned(publishes=2)
        rollout_service = RolloutService(version_service, strategy="FULL", percentage=100)
        rollout = rollout_service.start("policy-1", 2)

        with pytest.raises(Error):
            rollout_service.start("policy-1", 2)

        # stopping frees the policy up for a new rollout
        rollout_service.stop(rollout.rollout_id)
        second = rollout_service.start("policy-1", 2)

        assert second.rollout_id != rollout.rollout_id
        assert rollout_service.status(second.rollout_id) == "RUNNING"
