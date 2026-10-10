import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
)


class FakeClock:
    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current


def _binding(binding_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id="development",
        capability_id=f"capability-{binding_id}",
        created_at=datetime.now(timezone.utc),
    )


def _group(group_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_id,
        binding_ids=binding_ids,
    )


def _build_context(binding_ids=("binding-1", "binding-2"), active_binding_ids=None, group_binding_ids=("binding-1", "binding-2")):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

    for binding_id in binding_ids:
        binding_registry.register(_binding(binding_id))

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_registry,
        FakeClock(datetime.now(timezone.utc)),
    )

    for binding_id in active_binding_ids if active_binding_ids is not None else binding_ids:
        activation_service.activate(binding_id)

    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()
    group_registry.register(_group("group-1", binding_ids=group_binding_ids))

    group_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionService(
        group_registry
    )

    deployment_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentService(
        group_version_service,
        binding_registry,
        activation_service,
    )

    return deployment_service, group_version_service, group_registry, binding_registry, activation_service


def _request(group_id="group-1", version="v1", target_environment="production"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRequest(
        group_id=group_id,
        version=version,
        target_environment=target_environment,
    )


class TestDeployGroup:
    def test_deploy_group(self):
        deployment_service, group_version_service, *_ = _build_context()
        group_version_service.publish("group-1", "v1")

        result = deployment_service.deploy(_request())

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentResult)
        assert result.successful is True
        assert result.deployed_bindings == ("binding-1", "binding-2")
        assert deployment_service.deployment("group-1") == result


class TestRedeployGroup:
    def test_redeploy_group(self):
        deployment_service, group_version_service, group_registry, *_ = _build_context()
        group_version_service.publish("group-1", "v1")
        first = deployment_service.deploy(_request())

        group_registry.replace(_group("group-1", binding_ids=("binding-2",)))
        group_version_service.publish("group-1", "v2")

        redeployed = deployment_service.redeploy("group-1")

        assert redeployed.deployment_id == first.deployment_id
        assert redeployed.deployed_bindings == ("binding-2",)
        assert deployment_service.deployment("group-1") == redeployed

    def test_redeploy_without_active_deployment_raises(self):
        deployment_service, group_version_service, *_ = _build_context()
        group_version_service.publish("group-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            deployment_service.redeploy("group-1")


class TestUndeployGroup:
    def test_undeploy_group(self):
        deployment_service, group_version_service, *_ = _build_context()
        group_version_service.publish("group-1", "v1")
        deployment_service.deploy(_request())

        deployment_service.undeploy("group-1")

        assert deployment_service.deployment("group-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            deployment_service.undeploy("group-1")


class TestAtomicDeploymentFailure:
    def test_inactive_member_fails_whole_deployment(self):
        deployment_service, group_version_service, *_ = _build_context(active_binding_ids=("binding-1",))
        group_version_service.publish("group-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            deployment_service.deploy(_request())

        assert deployment_service.deployment("group-1") is None

    def test_unknown_member_fails_whole_deployment(self):
        deployment_service, group_version_service, *_ = _build_context(
            binding_ids=("binding-1",),
            active_binding_ids=("binding-1",),
            group_binding_ids=("binding-1", "binding-missing"),
        )
        group_version_service.publish("group-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            deployment_service.deploy(_request())

        assert deployment_service.deployment("group-1") is None


class TestDeploymentLookup:
    def test_deployment_lookup(self):
        deployment_service, group_version_service, *_ = _build_context()

        assert deployment_service.deployment("group-1") is None

        group_version_service.publish("group-1", "v1")
        result = deployment_service.deploy(_request())

        assert deployment_service.deployment("group-1") == result

    def test_reject_blank_group_id(self):
        deployment_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            deployment_service.deployment("   ")


class TestDuplicateDeploymentRejection:
    def test_duplicate_active_deployment_rejected(self):
        deployment_service, group_version_service, *_ = _build_context()
        group_version_service.publish("group-1", "v1")
        deployment_service.deploy(_request())

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            deployment_service.deploy(_request())


class TestImmutableDeploymentResult:
    def test_immutable_result(self):
        deployment_service, group_version_service, *_ = _build_context()
        group_version_service.publish("group-1", "v1")

        result = deployment_service.deploy(_request())

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False


class TestRejectInvalidRequests:
    def test_reject_none_request(self):
        deployment_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            deployment_service.deploy(None)

    def test_reject_blank_request_fields(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            _request(group_id="   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            _request(version=None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            _request(target_environment="   ")

    def test_reject_unknown_group_or_version(self):
        deployment_service, group_version_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            deployment_service.deploy(_request(group_id="group-missing"))

        group_version_service.publish("group-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            deployment_service.deploy(_request(version="v-missing"))

    def test_reject_stale_unreleased_version(self):
        deployment_service, group_version_service, group_registry, *_ = _build_context()
        group_version_service.publish("group-1", "v1")

        group_registry.replace(_group("group-1", binding_ids=("binding-2",)))
        group_version_service.publish("group-1", "v2")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            deployment_service.deploy(_request(version="v1"))

    def test_reject_none_dependencies(self):
        deployment_service, group_version_service, _, binding_registry, activation_service = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentService(
                None, binding_registry, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentService(
                group_version_service, None, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentService(
                group_version_service, binding_registry, None
            )
