import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy as Policy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyService as PolicyService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyResolution as Resolution,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion as Version,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionService as VersionService,
)


class _ConfigurationProvider:
    def __init__(self, configurations):
        self._configurations = list(configurations)
        self._index = 0

    def __call__(self, policy_id):
        configuration = self._configurations[self._index]
        self._index += 1
        return configuration


def _policy_service_with(policy_id="policy-1", session_id="session-1"):
    policy_service = PolicyService()
    policy_service.register(
        Policy(policy_id=policy_id, name="standard", max_runtime=3600, max_idle=300, allow_restore=True, enabled=True)
    )
    policy_service.assign(session_id, policy_id)

    return policy_service


class TestWorkspaceSessionPolicyVersionService:
    def test_publish_version(self):
        policy_service = _policy_service_with()
        provider = _ConfigurationProvider([{"max_runtime": 3600}])
        service = VersionService(policy_service, provider)

        version = service.publish("policy-1")

        assert isinstance(version, Version)
        assert version.policy_id == "policy-1"
        assert version.version == 1
        assert version.configuration == {"max_runtime": 3600}

        with pytest.raises(Error):
            service.publish("   ")

    def test_resolve_version(self):
        policy_service = _policy_service_with()
        provider = _ConfigurationProvider([{"max_runtime": 3600}])
        service = VersionService(policy_service, provider)
        service.publish("policy-1")

        resolution = service.resolve("session-1")

        assert isinstance(resolution, Resolution)
        assert resolution.session_id == "session-1"
        assert resolution.policy_id == "policy-1"
        assert resolution.version == 1

        with pytest.raises(Error):
            service.resolve("session-without-a-policy")

    def test_version_history(self):
        policy_service = _policy_service_with()
        provider = _ConfigurationProvider(
            [{"max_runtime": 3600}, {"max_runtime": 1800}, {"max_runtime": 900}]
        )
        service = VersionService(policy_service, provider)

        service.publish("policy-1")
        service.publish("policy-1")
        service.publish("policy-1")

        history = service.history("policy-1")

        assert [v.version for v in history] == [1, 2, 3]
        assert [v.configuration["max_runtime"] for v in history] == [3600, 1800, 900]

        assert service.history("never-published") == ()

    def test_rollback(self):
        policy_service = _policy_service_with()
        provider = _ConfigurationProvider([{"max_runtime": 3600}, {"max_runtime": 1800}])
        service = VersionService(policy_service, provider)

        service.publish("policy-1")
        service.publish("policy-1")

        rolled_back = service.rollback("policy-1", 1)

        assert rolled_back.version == 3
        assert rolled_back.configuration == {"max_runtime": 3600}

        # rollback preserves every prior version rather than removing them
        history = service.history("policy-1")
        assert [v.version for v in history] == [1, 2, 3]

        assert service.latest("policy-1") == rolled_back

        with pytest.raises(Error):
            service.rollback("policy-1", 99)

    def test_running_session_unchanged(self):
        policy_service = _policy_service_with()
        provider = _ConfigurationProvider([{"max_runtime": 3600}, {"max_runtime": 1800}])
        service = VersionService(policy_service, provider)

        service.publish("policy-1")
        resolution = service.resolve("session-1")
        assert resolution.version == 1

        service.publish("policy-1")

        # the already-resolved session stays bound to version 1
        assert service.resolve("session-1").version == 1
        assert service.latest("policy-1").version == 2

    def test_latest_lookup(self):
        policy_service = _policy_service_with()
        provider = _ConfigurationProvider([{"max_runtime": 3600}, {"max_runtime": 1800}])
        service = VersionService(policy_service, provider)

        with pytest.raises(Error):
            service.latest("policy-1")

        service.publish("policy-1")
        first_latest = service.latest("policy-1")
        assert first_latest.version == 1

        service.publish("policy-1")
        second_latest = service.latest("policy-1")
        assert second_latest.version == 2
