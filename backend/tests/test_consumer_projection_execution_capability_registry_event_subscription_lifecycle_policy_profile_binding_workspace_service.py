from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSnapshot,
)


def _binding(binding_id, profile_id="development", capability_id="capability-a"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id=profile_id,
        capability_id=capability_id,
        created_at=datetime.now(timezone.utc),
    )


def _template(template_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=binding_ids,
        metadata={},
    )


def _preset(preset_id, binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=preset_id,
        description="A preset.",
        binding_template_ids=binding_template_ids,
    )


def _group(group_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_id,
        binding_ids=binding_ids,
    )


def _build_service():
    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    template_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    preset_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    group_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    for binding_id in ("binding-1", "binding-2"):
        binding_service.register(_binding(binding_id))

    for template_id in ("template-1", "template-2"):
        template_service.register(_template(template_id, binding_ids=("binding-1",)))

    for preset_id in ("preset-1",):
        preset_service.register(_preset(preset_id, binding_template_ids=("template-1",)))

    for group_id in ("group-1",):
        group_service.register(_group(group_id, binding_ids=("binding-1",)))

    workspace_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService(
        binding_service, template_service, preset_service, group_service
    )

    return workspace_service


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


class TestProfileBindingWorkspaceService:
    def test_create_workspace(self):
        service = _build_service()

        workspace = _workspace(
            "workspace-1",
            binding_ids=("binding-1",),
            template_ids=("template-1",),
            preset_ids=("preset-1",),
            group_ids=("group-1",),
        )
        created = service.create(workspace)

        assert created == workspace
        assert service.find("workspace-1") == workspace

    def test_update_workspace(self):
        service = _build_service()

        service.create(_workspace("workspace-1", binding_ids=("binding-1",)))

        updated = _workspace(
            "workspace-1",
            name="renamed",
            binding_ids=("binding-1", "binding-2"),
            template_ids=("template-1",),
        )
        service.update(updated)

        assert service.find("workspace-1") == updated

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.update(_workspace("workspace-unknown"))

    def test_delete_workspace(self):
        service = _build_service()

        service.create(_workspace("workspace-1", binding_ids=("binding-1",)))

        service.delete("workspace-1")

        assert service.find("workspace-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.delete("workspace-1")

    def test_clone_workspace(self):
        service = _build_service()

        service.create(
            _workspace(
                "workspace-1",
                binding_ids=("binding-1",),
                template_ids=("template-1",),
                preset_ids=("preset-1",),
                group_ids=("group-1",),
            )
        )

        cloned = service.clone("workspace-1")

        assert cloned.workspace_id != "workspace-1"
        assert cloned.name == "workspace-1"
        assert cloned.binding_ids == ("binding-1",)
        assert cloned.template_ids == ("template-1",)
        assert cloned.preset_ids == ("preset-1",)
        assert cloned.group_ids == ("group-1",)
        assert service.find(cloned.workspace_id) == cloned

    def test_cloned_workspace_is_independent(self):
        service = _build_service()

        service.create(_workspace("workspace-1", binding_ids=("binding-1",)))
        cloned = service.clone("workspace-1")

        service.update(_workspace("workspace-1", binding_ids=("binding-1", "binding-2")))

        assert service.find(cloned.workspace_id).binding_ids == ("binding-1",)
        assert service.find("workspace-1").binding_ids == ("binding-1", "binding-2")

    def test_clone_missing_workspace_rejected(self):
        service = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.clone("workspace-missing")

    def test_snapshot_generation(self):
        service = _build_service()

        service.create(
            _workspace(
                "workspace-1",
                binding_ids=("binding-1", "binding-2"),
                template_ids=("template-1",),
                preset_ids=("preset-1",),
                group_ids=(),
            )
        )

        snapshot = service.snapshot("workspace-1")

        assert isinstance(
            snapshot,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSnapshot,
        )
        assert snapshot.workspace_id == "workspace-1"
        assert snapshot.resource_counts == {
            "bindings": 2,
            "templates": 1,
            "presets": 1,
            "groups": 0,
        }

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.snapshot("workspace-missing")

    def test_lookup_and_list(self):
        service = _build_service()

        first = service.create(_workspace("workspace-1", binding_ids=("binding-1",)))
        second = service.create(_workspace("workspace-2", binding_ids=("binding-2",)))

        assert service.find("workspace-1") == first
        assert service.find("workspace-missing") is None
        assert service.list() == (first, second)

    def test_duplicate_workspace_id_rejection(self):
        service = _build_service()

        service.create(_workspace("workspace-1", binding_ids=("binding-1",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.create(_workspace("workspace-1", binding_ids=("binding-2",)))

    def test_reject_invalid_workspaces(self):
        service = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.create(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            _workspace("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.create(_workspace("workspace-1", binding_ids=("binding-unknown",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.create(_workspace("workspace-1", template_ids=("template-unknown",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.create(_workspace("workspace-1", preset_ids=("preset-unknown",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.create(_workspace("workspace-1", group_ids=("group-unknown",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.find("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            service.delete("   ")

    def test_reject_invalid_constructor_arguments(self):
        binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
        template_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
        preset_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
        group_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService(
                None, template_service, preset_service, group_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService(
                binding_service, None, preset_service, group_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService(
                binding_service, template_service, None, group_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService(
                binding_service, template_service, preset_service, None
            )

    def test_ordering_preserved(self):
        service = _build_service()

        first = service.create(
            _workspace(
                "workspace-1",
                binding_ids=("binding-2", "binding-1"),
            )
        )

        assert first.binding_ids == ("binding-2", "binding-1")

    def test_duplicate_member_rejection(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError):
            _workspace("workspace-1", binding_ids=("binding-1", "binding-1"))
