import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
)


class FakeClock:
    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current


def _template(template_id, binding_ids=("binding-1",)):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=binding_ids,
        metadata={},
    )


def _preset(preset_id, description="A preset.", binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=preset_id,
        description=description,
        binding_template_ids=binding_template_ids,
    )


def _build_context(template_ids=("template-1", "template-2", "template-3"), active_template_ids=None):
    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

    for template_id in template_ids:
        template_registry.register(_template(template_id))

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        template_registry,
        FakeClock(datetime.now(timezone.utc)),
    )

    for template_id in active_template_ids if active_template_ids is not None else template_ids:
        activation_service.activate(template_id)

    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

    return preset_registry, template_registry, activation_service


class TestProfileBindingPresetResolver:
    def test_resolve_existing_preset(self):
        preset_registry, template_registry, activation_service = _build_context()
        preset_registry.register(_preset("preset-1", binding_template_ids=("template-1", "template-2")))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        result = resolver.resolve("preset-1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult)
        assert result.resolved is True
        assert result.preset == preset_registry.find("preset-1")
        assert result.templates == (template_registry.find("template-1"), template_registry.find("template-2"))
        assert result.source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource.REGISTRY

    def test_resolve_missing_preset(self):
        preset_registry, template_registry, activation_service = _build_context()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        result = resolver.resolve("preset-does-not-exist")

        assert result.resolved is False
        assert result.preset is None
        assert result.templates == ()
        assert result.source is None

    def test_resolve_missing_uses_default(self):
        preset_registry, template_registry, activation_service = _build_context()
        default_preset = _preset("preset-default", binding_template_ids=("template-1",))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry,
            template_registry,
            activation_service,
            default_preset=default_preset,
        )

        result = resolver.resolve("preset-does-not-exist")

        assert result.resolved is True
        assert result.preset is default_preset
        assert result.templates == (template_registry.find("template-1"),)
        assert result.source == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource.DEFAULT

    def test_resolve_active_members_only(self):
        preset_registry, template_registry, activation_service = _build_context(
            template_ids=("template-1", "template-2", "template-3"),
            active_template_ids=("template-1", "template-3"),
        )
        preset_registry.register(_preset("preset-1", binding_template_ids=("template-1", "template-2", "template-3")))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        result = resolver.resolve("preset-1")

        assert result.templates == (template_registry.find("template-1"), template_registry.find("template-3"))

    def test_ignore_inactive_and_missing_members(self):
        preset_registry, template_registry, activation_service = _build_context(
            template_ids=("template-1", "template-2"),
            active_template_ids=("template-1",),
        )
        preset_registry.register(
            _preset("preset-1", binding_template_ids=("template-1", "template-2", "template-missing"))
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        result = resolver.resolve("preset-1")

        assert result.templates == (template_registry.find("template-1"),)

    def test_resolve_or_raise_success(self):
        preset_registry, template_registry, activation_service = _build_context()
        preset = _preset("preset-1", binding_template_ids=("template-1",))
        preset_registry.register(preset)

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        assert resolver.resolve_or_raise("preset-1") == preset

    def test_resolve_or_raise_failure(self):
        preset_registry, template_registry, activation_service = _build_context()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError):
            resolver.resolve_or_raise("preset-does-not-exist")

    def test_contains_true_and_false(self):
        preset_registry, template_registry, activation_service = _build_context()
        preset_registry.register(_preset("preset-1", binding_template_ids=("template-1",)))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        assert resolver.contains("preset-1") is True
        assert resolver.contains("preset-does-not-exist") is False

    def test_resolve_templates(self):
        preset_registry, template_registry, activation_service = _build_context(
            template_ids=("template-1", "template-2"),
            active_template_ids=("template-1", "template-2"),
        )
        preset_registry.register(_preset("preset-1", binding_template_ids=("template-2", "template-1")))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        assert resolver.resolve_templates("preset-1") == (template_registry.find("template-2"), template_registry.find("template-1"))
        assert resolver.resolve_templates("preset-does-not-exist") == ()

    def test_immutable_result(self):
        preset_registry, template_registry, activation_service = _build_context()
        preset_registry.register(_preset("preset-1", binding_template_ids=("template-1",)))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        result = resolver.resolve("preset-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resolved = False

    def test_does_not_mutate_registries(self):
        preset_registry, template_registry, activation_service = _build_context()
        preset_registry.register(_preset("preset-1", binding_template_ids=("template-1",)))

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        resolver.resolve("preset-1")
        resolver.resolve("preset-does-not-exist")

        assert len(preset_registry.list()) == 1
        assert len(template_registry.list()) == 3

    def test_reject_none_dependencies(self):
        preset_registry, template_registry, activation_service = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
                None, template_registry, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
                preset_registry, None, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
                preset_registry, template_registry, None
            )

    def test_reject_blank_preset_id(self):
        preset_registry, template_registry, activation_service = _build_context()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            preset_registry, template_registry, activation_service
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError):
            resolver.resolve("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError):
            resolver.resolve(None)

    def test_reject_corrupted_preset_membership(self):
        preset_registry, template_registry, activation_service = _build_context()

        class CorruptedRegistry:
            def find(self, preset_id):
                return object()

        resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver(
            CorruptedRegistry(), template_registry, activation_service
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError):
            resolver.resolve("preset-1")

    def test_reject_invalid_resolution_source(self):
        preset = _preset("preset-1", binding_template_ids=("template-1",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult(
                preset=preset,
                templates=(),
                resolved=True,
                source="not-a-real-source",
            )

    def test_reject_malformed_result(self):
        preset = _preset("preset-1", binding_template_ids=("template-1",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult(
                preset=None,
                templates=(),
                resolved=True,
                source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource.REGISTRY,
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult(
                preset=preset,
                templates=(),
                resolved=False,
                source=None,
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResultError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult(
                preset=None,
                templates=(),
                resolved=False,
                source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource.REGISTRY,
            )
