import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistrySnapshot,
)


def _preset(preset_id, name=None, description="A preset.", binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=name or preset_id,
        description=description,
        binding_template_ids=binding_template_ids,
    )


class TestProfileBindingPresetRegistryService:
    def test_register_preset(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

        preset = _preset("preset-1", binding_template_ids=("template-1",))
        service.register(preset)

        assert service.find("preset-1") == preset

    def test_replace_preset(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

        original = _preset("preset-1", binding_template_ids=("template-1",))
        service.register(original)

        replacement = _preset("preset-1", binding_template_ids=("template-1", "template-2"))
        service.replace(replacement)

        assert service.find("preset-1") == replacement
        assert service.list() == (replacement,)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError):
            service.replace(_preset("preset-unknown", binding_template_ids=("template-1",)))

    def test_remove_preset(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

        preset = _preset("preset-1", binding_template_ids=("template-1",))
        service.register(preset)

        service.remove("preset-1")

        assert service.find("preset-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError):
            service.remove("preset-1")

    def test_lookup_existing_and_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

        preset = _preset("preset-1", binding_template_ids=("template-1",))
        service.register(preset)

        assert service.find("preset-1") == preset
        assert service.find("preset-missing") is None

    def test_contains(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

        preset = _preset("preset-1", binding_template_ids=("template-1",))
        service.register(preset)

        assert service.contains("preset-1") is True
        assert service.contains("preset-missing") is False

    def test_list_preserves_registration_order(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

        first = _preset("preset-1", binding_template_ids=("template-1",))
        second = _preset("preset-2", binding_template_ids=("template-2",))
        service.register(first)
        service.register(second)

        assert service.list() == (first, second)

    def test_snapshot_generation(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

        service.register(_preset("preset-1", binding_template_ids=("template-1", "template-2")))
        service.register(_preset("preset-2", binding_template_ids=("template-2", "template-3")))

        snapshot = service.snapshot()

        assert isinstance(snapshot, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistrySnapshot)
        assert snapshot.preset_count == 2
        assert snapshot.template_count == 3

    def test_immutable_registry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

        first = _preset("preset-1", binding_template_ids=("template-1",))
        service.register(first)

        registry_snapshot = service.list()

        service.register(_preset("preset-2", binding_template_ids=("template-2",)))

        assert registry_snapshot == (first,)
        assert len(service.list()) == 2

        with pytest.raises(AttributeError):
            first.name = "renamed"

    def test_duplicate_rejection(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

        service.register(_preset("preset-1", binding_template_ids=("template-1",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError):
            service.register(_preset("preset-1", binding_template_ids=("template-2",)))

    def test_reject_invalid_operations(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError):
            service.register(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError):
            service.remove("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError):
            service.remove("preset-missing")
