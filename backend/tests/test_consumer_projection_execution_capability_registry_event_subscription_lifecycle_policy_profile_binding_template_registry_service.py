import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistrySnapshot,
)


def _template(template_id, name=None, binding_ids=(), metadata=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=name or template_id,
        binding_ids=binding_ids,
        metadata=metadata or {},
    )


class TestProfileBindingTemplateRegistryService:
    def test_register_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

        template = _template("template-1", binding_ids=("binding-1",))
        service.register(template)

        assert service.find("template-1") == template

    def test_replace_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

        original = _template("template-1", binding_ids=("binding-1",))
        service.register(original)

        replacement = _template("template-1", binding_ids=("binding-1", "binding-2"))
        service.replace(replacement)

        assert service.find("template-1") == replacement
        assert service.list() == (replacement,)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError):
            service.replace(_template("template-unknown", binding_ids=("binding-1",)))

    def test_remove_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

        template = _template("template-1", binding_ids=("binding-1",))
        service.register(template)

        service.remove("template-1")

        assert service.find("template-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError):
            service.remove("template-1")

    def test_lookup_existing_and_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

        template = _template("template-1", binding_ids=("binding-1",))
        service.register(template)

        assert service.find("template-1") == template
        assert service.find("template-missing") is None

    def test_contains(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

        template = _template("template-1", binding_ids=("binding-1",))
        service.register(template)

        assert service.contains("template-1") is True
        assert service.contains("template-missing") is False

    def test_list_preserves_registration_order(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

        first = _template("template-1", binding_ids=("binding-1",))
        second = _template("template-2", binding_ids=("binding-2",))
        service.register(first)
        service.register(second)

        assert service.list() == (first, second)

    def test_snapshot_generation(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

        service.register(_template("template-1", binding_ids=("binding-1", "binding-2")))
        service.register(_template("template-2", binding_ids=("binding-2", "binding-3")))

        snapshot = service.snapshot()

        assert isinstance(snapshot, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistrySnapshot)
        assert snapshot.template_count == 2
        assert snapshot.binding_count == 3

    def test_immutable_registry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

        first = _template("template-1", binding_ids=("binding-1",))
        service.register(first)

        registry_snapshot = service.list()

        service.register(_template("template-2", binding_ids=("binding-2",)))

        assert registry_snapshot == (first,)
        assert len(service.list()) == 2

        with pytest.raises(AttributeError):
            first.name = "renamed"

    def test_duplicate_rejection(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

        service.register(_template("template-1", binding_ids=("binding-1",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError):
            service.register(_template("template-1", binding_ids=("binding-2",)))

    def test_reject_invalid_operations(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError):
            service.register(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError):
            service.remove("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError):
            service.remove("template-missing")
