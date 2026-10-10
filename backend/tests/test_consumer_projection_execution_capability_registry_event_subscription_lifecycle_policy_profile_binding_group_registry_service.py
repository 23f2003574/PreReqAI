import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistrySnapshot,
)


def _group(group_id, group_name=None, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_name or group_id,
        binding_ids=binding_ids,
    )


class TestProfileBindingGroupRegistryService:
    def test_register_group(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        group = _group("group-1", binding_ids=("binding-1",))
        service.register(group)

        assert service.find("group-1") == group

    def test_replace_group(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        original = _group("group-1", binding_ids=("binding-1",))
        service.register(original)

        replacement = _group("group-1", binding_ids=("binding-1", "binding-2"))
        service.replace(replacement)

        assert service.find("group-1") == replacement
        assert service.list() == (replacement,)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError):
            service.replace(_group("group-unknown", binding_ids=("binding-1",)))

    def test_remove_group(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        group = _group("group-1", binding_ids=("binding-1",))
        service.register(group)

        service.remove("group-1")

        assert service.find("group-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError):
            service.remove("group-1")

    def test_lookup_existing_and_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        group = _group("group-1", binding_ids=("binding-1",))
        service.register(group)

        assert service.find("group-1") == group
        assert service.find("group-missing") is None

    def test_contains(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        group = _group("group-1", binding_ids=("binding-1",))
        service.register(group)

        assert service.contains("group-1") is True
        assert service.contains("group-missing") is False

    def test_list_preserves_registration_order(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        first = _group("group-1", binding_ids=("binding-1",))
        second = _group("group-2", binding_ids=("binding-2",))
        service.register(first)
        service.register(second)

        assert service.list() == (first, second)

    def test_snapshot_generation(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        service.register(_group("group-1", binding_ids=("binding-1", "binding-2")))
        service.register(_group("group-2", binding_ids=("binding-2", "binding-3")))

        snapshot = service.snapshot()

        assert isinstance(snapshot, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistrySnapshot)
        assert snapshot.group_count == 2
        assert snapshot.binding_count == 3

    def test_immutable_registry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        first = _group("group-1", binding_ids=("binding-1",))
        service.register(first)

        registry_snapshot = service.list()

        service.register(_group("group-2", binding_ids=("binding-2",)))

        assert registry_snapshot == (first,)
        assert len(service.list()) == 2

        with pytest.raises(AttributeError):
            first.group_name = "renamed"

    def test_duplicate_rejection(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        service.register(_group("group-1", binding_ids=("binding-1",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError):
            service.register(_group("group-1", binding_ids=("binding-2",)))

    def test_reject_invalid_operations(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError):
            service.register(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError):
            service.remove("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError):
            service.remove("group-missing")
