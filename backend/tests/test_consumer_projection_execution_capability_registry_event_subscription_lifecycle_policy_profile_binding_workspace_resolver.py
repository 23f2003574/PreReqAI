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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError,
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
        capability_id="capability-a",
        created_at=datetime.now(timezone.utc),
    )


def _template(template_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=(),
        metadata={},
    )


def _preset(preset_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=preset_id,
        description="A preset.",
        binding_template_ids=(),
    )


def _group(group_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_id,
        binding_ids=(),
    )


def _workspace(
    workspace_id,
    binding_ids=(),
    template_ids=(),
    preset_ids=(),
    group_ids=(),
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace(
        workspace_id=workspace_id,
        name=workspace_id,
        description="A workspace.",
        binding_ids=binding_ids,
        template_ids=template_ids,
        preset_ids=preset_ids,
        group_ids=group_ids,
    )


def _build_context(
    binding_ids=("binding-1", "binding-2"),
    active_binding_ids=None,
    template_ids=("template-1", "template-2"),
    active_template_ids=None,
    preset_ids=("preset-1",),
    active_preset_ids=None,
    group_ids=("group-1",),
    active_group_ids=None,
):
    clock = FakeClock(datetime.now(timezone.utc))

    workspace_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()

    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    for binding_id in binding_ids:
        binding_registry.register(_binding(binding_id))
    binding_activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(binding_registry, clock)
    for binding_id in active_binding_ids if active_binding_ids is not None else binding_ids:
        binding_activation_service.activate(binding_id)

    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    for template_id in template_ids:
        template_registry.register(_template(template_id))
    template_activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(template_registry, clock)
    for template_id in active_template_ids if active_template_ids is not None else template_ids:
        template_activation_service.activate(template_id)

    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    for preset_id in preset_ids:
        preset_registry.register(_preset(preset_id))
    preset_activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(preset_registry, clock)
    for preset_id in active_preset_ids if active_preset_ids is not None else preset_ids:
        preset_activation_service.activate(preset_id)

    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()
    for group_id in group_ids:
        group_registry.register(_group(group_id))
    group_activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(group_registry, clock)
    for group_id in active_group_ids if active_group_ids is not None else group_ids:
        group_activation_service.activate(group_id)

    return {
        "workspace_registry": workspace_registry,
        "binding_registry": binding_registry,
        "binding_activation_service": binding_activation_service,
        "template_registry": template_registry,
        "template_activation_service": template_activation_service,
        "preset_registry": preset_registry,
        "preset_activation_service": preset_activation_service,
        "group_registry": group_registry,
        "group_activation_service": group_activation_service,
    }


def _build_resolver(context, default_workspace=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolver(
        context["workspace_registry"],
        context["binding_registry"],
        context["binding_activation_service"],
        context["template_registry"],
        context["template_activation_service"],
        context["preset_registry"],
        context["preset_activation_service"],
        context["group_registry"],
        context["group_activation_service"],
        default_workspace=default_workspace,
    )


class TestProfileBindingWorkspaceResolver:
    def test_resolve_existing_workspace(self):
        context = _build_context()
        workspace = _workspace(
            "workspace-1",
            binding_ids=("binding-1", "binding-2"),
            template_ids=("template-1",),
            preset_ids=("preset-1",),
            group_ids=("group-1",),
        )
        context["workspace_registry"].register(workspace)

        resolver = _build_resolver(context)

        result = resolver.resolve("workspace-1")

        assert result.resolved is True
        assert result.workspace == workspace
        assert result.resource_counts == {"bindings": 2, "templates": 1, "presets": 1, "groups": 1}
        assert result.source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionSource.REGISTRY

    def test_resolve_missing_workspace(self):
        context = _build_context()
        resolver = _build_resolver(context)

        result = resolver.resolve("workspace-missing")

        assert result.resolved is False
        assert result.workspace is None
        assert result.resource_counts == {}
        assert result.source is None

    def test_resolve_missing_uses_default(self):
        context = _build_context()
        default_workspace = _workspace("workspace-default", binding_ids=("binding-1",))

        resolver = _build_resolver(context, default_workspace=default_workspace)

        result = resolver.resolve("workspace-missing")

        assert result.resolved is True
        assert result.workspace is default_workspace
        assert result.source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolutionSource.DEFAULT

    def test_resolve_resources(self):
        context = _build_context()
        workspace = _workspace(
            "workspace-1",
            binding_ids=("binding-2", "binding-1"),
            template_ids=("template-1",),
            preset_ids=("preset-1",),
            group_ids=("group-1",),
        )
        context["workspace_registry"].register(workspace)

        resolver = _build_resolver(context)

        resources = resolver.resolve_resources("workspace-1")

        assert resources["bindings"] == (
            context["binding_registry"].find("binding-2"),
            context["binding_registry"].find("binding-1"),
        )
        assert resources["templates"] == (context["template_registry"].find("template-1"),)
        assert resources["presets"] == (context["preset_registry"].find("preset-1"),)
        assert resources["groups"] == (context["group_registry"].find("group-1"),)

    def test_resolve_resources_missing_workspace(self):
        context = _build_context()
        resolver = _build_resolver(context)

        resources = resolver.resolve_resources("workspace-missing")

        assert resources == {"bindings": (), "templates": (), "presets": (), "groups": ()}

    def test_ignore_inactive_and_missing_resources(self):
        context = _build_context(
            binding_ids=("binding-1", "binding-2"),
            active_binding_ids=("binding-1",),
        )
        workspace = _workspace(
            "workspace-1",
            binding_ids=("binding-1", "binding-2", "binding-missing"),
        )
        context["workspace_registry"].register(workspace)

        resolver = _build_resolver(context)

        result = resolver.resolve("workspace-1")

        assert result.resource_counts["bindings"] == 1
        assert resolver.resolve_resources("workspace-1")["bindings"] == (
            context["binding_registry"].find("binding-1"),
        )

    def test_resolve_or_raise_success(self):
        context = _build_context()
        workspace = _workspace("workspace-1", binding_ids=("binding-1",))
        context["workspace_registry"].register(workspace)

        resolver = _build_resolver(context)

        assert resolver.resolve_or_raise("workspace-1") == workspace

    def test_resolve_or_raise_failure(self):
        context = _build_context()
        resolver = _build_resolver(context)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError):
            resolver.resolve_or_raise("workspace-missing")

    def test_contains_true_and_false(self):
        context = _build_context()
        context["workspace_registry"].register(_workspace("workspace-1", binding_ids=("binding-1",)))

        resolver = _build_resolver(context)

        assert resolver.contains("workspace-1") is True
        assert resolver.contains("workspace-missing") is False

    def test_immutable_result(self):
        context = _build_context()
        context["workspace_registry"].register(_workspace("workspace-1", binding_ids=("binding-1",)))

        resolver = _build_resolver(context)
        result = resolver.resolve("workspace-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resolved = False

    def test_does_not_mutate_registries(self):
        context = _build_context()
        context["workspace_registry"].register(_workspace("workspace-1", binding_ids=("binding-1",)))

        resolver = _build_resolver(context)

        resolver.resolve("workspace-1")
        resolver.resolve("workspace-missing")
        resolver.resolve_resources("workspace-1")

        assert len(context["workspace_registry"].list()) == 1
        assert len(context["binding_registry"].list()) == 2

    def test_reject_blank_workspace_id(self):
        context = _build_context()
        resolver = _build_resolver(context)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError):
            resolver.resolve("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError):
            resolver.resolve_resources("   ")

    def test_reject_none_collaborators(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResolver(
                None,
                context["binding_registry"],
                context["binding_activation_service"],
                context["template_registry"],
                context["template_activation_service"],
                context["preset_registry"],
                context["preset_activation_service"],
                context["group_registry"],
                context["group_activation_service"],
            )
