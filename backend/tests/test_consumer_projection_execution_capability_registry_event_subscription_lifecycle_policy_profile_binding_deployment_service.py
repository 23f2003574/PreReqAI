import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService,
)


class FakeClock:
    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current


def _build_profile(profile_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        description=f"Profile {profile_id}.",
        policy_identifiers=(f"policy-{profile_id}",),
    )


def _build_context(profile_id="profile-a"):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
    profile_service.register(_build_profile(profile_id))

    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService(profile_service)

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_service,
        FakeClock(datetime.now(timezone.utc)),
    )

    version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
    resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(profile_service)
    release_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseService(resolver, version_service)

    binding_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionService(
        binding_service,
        version_service,
        release_service,
    )

    deployment_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentService(
        binding_service,
        activation_service,
        binding_version_service,
        version_service,
        release_service,
    )

    return {
        "deployment_service": deployment_service,
        "binding_service": binding_service,
        "activation_service": activation_service,
        "version_service": version_service,
        "release_service": release_service,
        "binding_version_service": binding_version_service,
        "profile_id": profile_id,
    }


def _publish_and_release(context, version):
    context["version_service"].publish(
        context["profile_id"],
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
            version=version,
            policy_identifiers=(f"policy-{version}",),
            created_at=datetime.now(timezone.utc),
        ),
    )
    context["release_service"].release(context["profile_id"], version)


def _active_binding(context, capability_id="capability-a"):
    binding = context["binding_service"].bind(context["profile_id"], capability_id)
    context["activation_service"].activate(binding.binding_id)
    return binding


class TestDeployBinding:
    def test_deploy_binding(self):
        context = _build_context()
        _publish_and_release(context, "1.0.0")
        binding = _active_binding(context)

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest(
            binding_id=binding.binding_id,
            target_environment="production",
            version=None,
        )

        result = context["deployment_service"].deploy(request)

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentResult)
        assert result.binding_id == binding.binding_id
        assert result.deployed_version == "1.0.0"
        assert result.successful is True


class TestRedeployBinding:
    def test_redeploy_binding_picks_up_new_latest_version(self):
        context = _build_context()
        _publish_and_release(context, "1.0.0")
        binding = _active_binding(context)

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest(
            binding_id=binding.binding_id,
            target_environment="production",
            version=None,
        )
        first = context["deployment_service"].deploy(request)

        _publish_and_release(context, "2.0.0")

        second = context["deployment_service"].redeploy(binding.binding_id)

        assert second.deployment_id == first.deployment_id
        assert second.deployed_version == "2.0.0"
        assert context["deployment_service"].deployment(binding.binding_id) == second


class TestUndeployBinding:
    def test_undeploy_binding(self):
        context = _build_context()
        _publish_and_release(context, "1.0.0")
        binding = _active_binding(context)

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest(
            binding_id=binding.binding_id,
            target_environment="production",
            version=None,
        )
        context["deployment_service"].deploy(request)

        context["deployment_service"].undeploy(binding.binding_id)

        assert context["deployment_service"].deployment(binding.binding_id) is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError):
            context["deployment_service"].undeploy(binding.binding_id)


class TestDeploymentLookup:
    def test_deployment_lookup_none_when_not_deployed(self):
        context = _build_context()
        binding = _active_binding(context)

        assert context["deployment_service"].deployment(binding.binding_id) is None


class TestDuplicateDeploymentRejection:
    def test_reject_duplicate_active_deployment(self):
        context = _build_context()
        _publish_and_release(context, "1.0.0")
        binding = _active_binding(context)

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest(
            binding_id=binding.binding_id,
            target_environment="production",
            version=None,
        )
        context["deployment_service"].deploy(request)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError):
            context["deployment_service"].deploy(request)


class TestInactiveBindingRejection:
    def test_reject_inactive_binding(self):
        context = _build_context()
        _publish_and_release(context, "1.0.0")
        binding = context["binding_service"].bind(context["profile_id"], "capability-a")

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest(
            binding_id=binding.binding_id,
            target_environment="production",
            version=None,
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError):
            context["deployment_service"].deploy(request)

    def test_reject_unresolved_profile_version(self):
        context = _build_context()
        binding = _active_binding(context)

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest(
            binding_id=binding.binding_id,
            target_environment="production",
            version=None,
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError):
            context["deployment_service"].deploy(request)

    def test_reject_unknown_deployment_target(self):
        context = _build_context()

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest(
            binding_id="binding-missing",
            target_environment="production",
            version=None,
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError):
            context["deployment_service"].deploy(request)

    def test_reject_blank_ids(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest(
                binding_id="   ",
                target_environment="production",
                version=None,
            )

        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError):
            context["deployment_service"].deployment(None)


class TestImmutableDeploymentResults:
    def test_immutable_result(self):
        context = _build_context()
        _publish_and_release(context, "1.0.0")
        binding = _active_binding(context)

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest(
            binding_id=binding.binding_id,
            target_environment="production",
            version=None,
        )
        result = context["deployment_service"].deploy(request)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False
