import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
)


def _build_profile(profile_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        description=f"Profile {profile_id}.",
        policy_identifiers=(f"policy-{profile_id}",),
    )


def _build_service(profile_ids=("development", "staging")):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

    for profile_id in profile_ids:
        profile_service.register(_build_profile(profile_id))

    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService(profile_service)

    return binding_service, profile_service


class TestProfileBindingService:
    def test_create_binding(self):
        service, _ = _build_service()

        binding = service.bind("development", "capability-a")

        assert isinstance(binding, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding)
        assert binding.profile_id == "development"
        assert binding.capability_id == "capability-a"
        assert binding.created_at is not None
        assert binding.binding_id is not None

    def test_remove_binding(self):
        service, _ = _build_service()

        binding = service.bind("development", "capability-a")

        removed = service.unbind(binding.binding_id)

        assert removed == binding
        assert service.find(binding.binding_id) is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError):
            service.unbind(binding.binding_id)

    def test_lookup_by_binding_profile_capability(self):
        service, _ = _build_service()

        first = service.bind("development", "capability-a")
        second = service.bind("development", "capability-b")
        third = service.bind("staging", "capability-a")

        assert service.find(first.binding_id) == first
        assert service.find("unknown-binding") is None

        by_profile = service.find_by_profile("development")
        assert isinstance(by_profile, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection)
        assert by_profile.bindings == (first, second)

        by_capability = service.find_by_capability("capability-a")
        assert by_capability.bindings == (first, third)

    def test_list_bindings(self):
        service, _ = _build_service()

        first = service.bind("development", "capability-a")
        second = service.bind("staging", "capability-b")

        collection = service.list()

        assert isinstance(collection, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection)
        assert collection.bindings == (first, second)

    def test_multiple_capabilities_per_profile(self):
        service, _ = _build_service()

        service.bind("development", "capability-a")
        service.bind("development", "capability-b")

        assert len(service.find_by_profile("development").bindings) == 2

    def test_duplicate_rejection(self):
        service, _ = _build_service()

        service.bind("development", "capability-a")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError):
            service.bind("development", "capability-a")

    def test_reject_invalid_bindings(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError):
            service.bind("   ", "capability-a")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError):
            service.bind("development", None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError):
            service.bind("unknown-profile", "capability-a")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError):
            service.find("   ")

    def test_immutable_collection(self):
        service, _ = _build_service()

        service.bind("development", "capability-a")

        collection = service.list()

        with pytest.raises(AttributeError):
            collection.bindings = ()

        binding = service.find_by_profile("development").bindings[0]

        with pytest.raises(AttributeError):
            binding.capability_id = "capability-z"
