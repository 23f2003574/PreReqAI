from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCollection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
)


def _binding(binding_id, profile_id="development", capability_id="capability-a"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id=profile_id,
        capability_id=capability_id,
        created_at=datetime.now(timezone.utc),
    )


def _build_service(binding_ids=("binding-1", "binding-2", "binding-3")):
    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

    for binding_id in binding_ids:
        binding_service.register(_binding(binding_id))

    group_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupService(binding_service)

    return group_service, binding_service


def _group(group_id, group_name=None, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_name or group_id,
        binding_ids=binding_ids,
    )


class TestProfileBindingGroupService:
    def test_create_group(self):
        service, _ = _build_service()

        group = _group("group-1", binding_ids=("binding-1", "binding-2"))
        created = service.create(group)

        assert created == group
        assert service.find("group-1") == group

    def test_update_group(self):
        service, _ = _build_service()

        service.create(_group("group-1", binding_ids=("binding-1",)))

        updated = _group("group-1", group_name="renamed", binding_ids=("binding-1", "binding-3"))
        service.update(updated)

        assert service.find("group-1") == updated

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            service.update(_group("group-unknown"))

    def test_remove_group(self):
        service, _ = _build_service()

        service.create(_group("group-1", binding_ids=("binding-1",)))

        service.remove("group-1")

        assert service.find("group-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            service.remove("group-1")

    def test_add_binding(self):
        service, _ = _build_service()

        service.create(_group("group-1", binding_ids=("binding-1",)))

        updated = service.add_binding("group-1", "binding-2")

        assert updated.binding_ids == ("binding-1", "binding-2")
        assert service.find("group-1").binding_ids == ("binding-1", "binding-2")

    def test_remove_binding(self):
        service, _ = _build_service()

        service.create(_group("group-1", binding_ids=("binding-1", "binding-2")))

        updated = service.remove_binding("group-1", "binding-1")

        assert updated.binding_ids == ("binding-2",)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            service.remove_binding("group-1", "binding-unknown")

    def test_lookup_and_list(self):
        service, _ = _build_service()

        first = service.create(_group("group-1", binding_ids=("binding-1",)))
        second = service.create(_group("group-2", binding_ids=("binding-2",)))

        assert service.find("group-1") == first
        assert service.find("group-missing") is None

        collection = service.list()

        assert isinstance(collection, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCollection)
        assert collection.groups == (first, second)

    def test_binding_may_belong_to_multiple_groups(self):
        service, _ = _build_service()

        service.create(_group("group-1", binding_ids=("binding-1",)))
        service.create(_group("group-2", binding_ids=("binding-1",)))

        assert service.find("group-1").binding_ids == ("binding-1",)
        assert service.find("group-2").binding_ids == ("binding-1",)

    def test_duplicate_group_id_rejection(self):
        service, _ = _build_service()

        service.create(_group("group-1", binding_ids=("binding-1",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            service.create(_group("group-1", binding_ids=("binding-2",)))

    def test_duplicate_member_rejection(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            _group("group-1", binding_ids=("binding-1", "binding-1"))

        service.create(_group("group-1", binding_ids=("binding-1",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            service.add_binding("group-1", "binding-1")

    def test_reject_invalid_groups(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            service.create(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            _group("   ", binding_ids=("binding-1",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            service.create(_group("group-1", binding_ids=("binding-unknown",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            service.find("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError):
            service.remove("   ")

    def test_immutable_collections(self):
        service, _ = _build_service()

        service.create(_group("group-1", binding_ids=("binding-1",)))

        collection = service.list()

        with pytest.raises(AttributeError):
            collection.groups = ()

        group = collection.groups[0]

        with pytest.raises(AttributeError):
            group.group_name = "renamed"
