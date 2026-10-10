import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistrySnapshot,
)


def _workspace(
    workspace_id,
    name=None,
    description="A workspace.",
    binding_ids=(),
    template_ids=(),
    preset_ids=(),
    group_ids=(),
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace(
        workspace_id=workspace_id,
        name=name or workspace_id,
        description=description,
        binding_ids=binding_ids,
        template_ids=template_ids,
        preset_ids=preset_ids,
        group_ids=group_ids,
    )


class TestProfileBindingWorkspaceRegistryService:
    def test_register_workspace(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

        workspace = _workspace("workspace-1", binding_ids=("binding-1",))
        service.register(workspace)

        assert service.find("workspace-1") == workspace

    def test_replace_workspace(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

        original = _workspace("workspace-1", binding_ids=("binding-1",))
        service.register(original)

        replacement = _workspace("workspace-1", binding_ids=("binding-1", "binding-2"))
        service.replace(replacement)

        assert service.find("workspace-1") == replacement
        assert service.list() == (replacement,)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError):
            service.replace(_workspace("workspace-unknown"))

    def test_remove_workspace(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

        workspace = _workspace("workspace-1", binding_ids=("binding-1",))
        service.register(workspace)

        service.remove("workspace-1")

        assert service.find("workspace-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError):
            service.remove("workspace-1")

    def test_lookup_existing_and_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

        workspace = _workspace("workspace-1", binding_ids=("binding-1",))
        service.register(workspace)

        assert service.find("workspace-1") == workspace
        assert service.find("workspace-missing") is None

    def test_contains(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

        workspace = _workspace("workspace-1", binding_ids=("binding-1",))
        service.register(workspace)

        assert service.contains("workspace-1") is True
        assert service.contains("workspace-missing") is False

    def test_list_preserves_registration_order(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

        first = _workspace("workspace-1", binding_ids=("binding-1",))
        second = _workspace("workspace-2", binding_ids=("binding-2",))
        service.register(first)
        service.register(second)

        assert service.list() == (first, second)

    def test_snapshot_generation(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

        service.register(_workspace("workspace-1", binding_ids=("binding-1",)))
        service.register(_workspace("workspace-2", binding_ids=("binding-2",)))

        snapshot = service.snapshot()

        assert isinstance(
            snapshot,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistrySnapshot,
        )
        assert snapshot.workspace_count == 2
        assert snapshot.snapshot_count == 1

        second_snapshot = service.snapshot()

        assert second_snapshot.workspace_count == 2
        assert second_snapshot.snapshot_count == 2

    def test_immutable_registry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

        first = _workspace("workspace-1", binding_ids=("binding-1",))
        service.register(first)

        registry_snapshot = service.list()

        service.register(_workspace("workspace-2", binding_ids=("binding-2",)))

        assert registry_snapshot == (first,)
        assert len(service.list()) == 2

        with pytest.raises(AttributeError):
            first.name = "renamed"

    def test_duplicate_rejection(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

        service.register(_workspace("workspace-1", binding_ids=("binding-1",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError):
            service.register(_workspace("workspace-1", binding_ids=("binding-2",)))

    def test_reject_invalid_operations(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError):
            service.register(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError):
            service.remove("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError):
            service.remove("workspace-missing")
