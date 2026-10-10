from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCollection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateService,
)


def _binding(binding_id, profile_id="development", capability_id="capability-a"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id=profile_id,
        capability_id=capability_id,
        created_at=datetime.now(timezone.utc),
    )


def _template(template_id, name=None, binding_ids=(), metadata=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=name or template_id,
        binding_ids=binding_ids,
        metadata=metadata or {},
    )


def _preset(preset_id, name=None, description="A preset.", binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=name or preset_id,
        description=description,
        binding_template_ids=binding_template_ids,
    )


def _build_service(binding_ids=("binding-1", "binding-2", "binding-3")):
    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

    for binding_id in binding_ids:
        binding_service.register(_binding(binding_id))

    template_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateService(binding_service)

    template_service.register(_template("template-1", binding_ids=("binding-1",)))
    template_service.register(_template("template-2", binding_ids=("binding-2", "binding-3")))

    preset_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetService(template_service)

    return preset_service, template_service


class TestProfileBindingPresetService:
    def test_register_and_remove_preset(self):
        service, _ = _build_service()

        preset = _preset("preset-1", binding_template_ids=("template-1", "template-2"))
        registered = service.register(preset)

        assert registered == preset
        assert service.find("preset-1") == preset

        service.remove("preset-1")

        assert service.find("preset-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError):
            service.remove("preset-1")

    def test_replace_preset(self):
        service, _ = _build_service()

        service.register(_preset("preset-1", binding_template_ids=("template-1",)))

        replacement = _preset("preset-1", name="renamed", binding_template_ids=("template-1", "template-2"))
        service.replace(replacement)

        assert service.find("preset-1") == replacement

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError):
            service.replace(_preset("preset-unknown"))

    def test_instantiate_preset_preserves_template_order(self):
        service, _ = _build_service()

        service.register(
            _preset("preset-1", binding_template_ids=("template-2", "template-1"))
        )

        instances = service.instantiate("preset-1")

        assert isinstance(instances, tuple)
        assert len(instances) == 2
        assert all(
            isinstance(collection, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection)
            for collection in instances
        )
        assert len(instances[0].bindings) == 2
        assert len(instances[1].bindings) == 1

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError):
            service.instantiate("preset-unknown")

    def test_instantiate_produces_independent_binding_sets(self):
        service, _ = _build_service()

        service.register(_preset("preset-1", binding_template_ids=("template-1", "template-2")))

        first_run = service.instantiate("preset-1")
        second_run = service.instantiate("preset-1")

        first_ids = {instance.binding_id for collection in first_run for instance in collection.bindings}
        second_ids = {instance.binding_id for collection in second_run for instance in collection.bindings}

        assert first_ids.isdisjoint(second_ids)

    def test_lookup_and_list(self):
        service, _ = _build_service()

        first = service.register(_preset("preset-1", binding_template_ids=("template-1",)))
        second = service.register(_preset("preset-2", binding_template_ids=("template-2",)))

        assert service.find("preset-1") == first
        assert service.find("preset-missing") is None

        collection = service.list()

        assert isinstance(collection, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCollection)
        assert collection.presets == (first, second)

    def test_duplicate_preset_id_rejection(self):
        service, _ = _build_service()

        service.register(_preset("preset-1", binding_template_ids=("template-1",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError):
            service.register(_preset("preset-1", binding_template_ids=("template-2",)))

    def test_reject_invalid_presets(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError):
            service.register(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError):
            _preset("   ", binding_template_ids=("template-1",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError):
            service.register(_preset("preset-1", binding_template_ids=("template-unknown",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError):
            service.find("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError):
            service.remove("   ")

    def test_immutable_collections(self):
        service, _ = _build_service()

        service.register(_preset("preset-1", binding_template_ids=("template-1",)))

        collection = service.list()

        with pytest.raises(AttributeError):
            collection.presets = ()

        preset = collection.presets[0]

        with pytest.raises(AttributeError):
            preset.name = "renamed"
