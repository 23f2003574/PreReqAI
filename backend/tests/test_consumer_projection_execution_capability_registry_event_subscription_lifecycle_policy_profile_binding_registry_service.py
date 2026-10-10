from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistrySnapshot,
)


def _binding(binding_id, profile_id, capability_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id=profile_id,
        capability_id=capability_id,
        created_at=datetime.now(timezone.utc),
    )


class TestProfileBindingRegistryService:
    def test_register_binding(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

        binding = _binding("binding-1", "development", "capability-a")
        service.register(binding)

        assert service.find("binding-1") == binding

    def test_replace_binding(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

        original = _binding("binding-1", "development", "capability-a")
        service.register(original)

        replacement = _binding("binding-1", "staging", "capability-a")
        service.replace(replacement)

        assert service.find("binding-1") == replacement
        assert service.list() == (replacement,)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError):
            service.replace(_binding("binding-unknown", "development", "capability-a"))

    def test_remove_binding(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

        binding = _binding("binding-1", "development", "capability-a")
        service.register(binding)

        service.remove("binding-1")

        assert service.find("binding-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError):
            service.remove("binding-1")

    def test_lookup_existing_and_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

        binding = _binding("binding-1", "development", "capability-a")
        service.register(binding)

        assert service.find("binding-1") == binding
        assert service.find("binding-missing") is None

    def test_contains(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

        binding = _binding("binding-1", "development", "capability-a")
        service.register(binding)

        assert service.contains("binding-1") is True
        assert service.contains("binding-missing") is False

    def test_snapshot_generation(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

        service.register(_binding("binding-1", "development", "capability-a"))
        service.register(_binding("binding-2", "development", "capability-b"))
        service.register(_binding("binding-3", "staging", "capability-a"))

        snapshot = service.snapshot()

        assert isinstance(snapshot, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistrySnapshot)
        assert snapshot.binding_count == 3
        assert snapshot.profile_count == 2
        assert snapshot.capability_count == 2

    def test_immutable_registry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

        first = _binding("binding-1", "development", "capability-a")
        service.register(first)

        registry_snapshot = service.list()

        service.register(_binding("binding-2", "staging", "capability-b"))

        assert registry_snapshot == (first,)
        assert len(service.list()) == 2

        with pytest.raises(AttributeError):
            first.profile_id = "staging"

    def test_duplicate_rejection(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

        service.register(_binding("binding-1", "development", "capability-a"))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError):
            service.register(_binding("binding-1", "staging", "capability-b"))

    def test_reject_invalid_operations(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError):
            service.register(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError):
            service.remove("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError):
            service.remove("binding-missing")
