from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCollection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateService,
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

    template_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateService(binding_service)

    return template_service, binding_service


def _template(template_id, name=None, binding_ids=(), metadata=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=name or template_id,
        binding_ids=binding_ids,
        metadata=metadata or {},
    )


class TestProfileBindingTemplateService:
    def test_register_and_remove_template(self):
        service, _ = _build_service()

        template = _template("template-1", binding_ids=("binding-1", "binding-2"))
        registered = service.register(template)

        assert registered == template
        assert service.find("template-1") == template

        service.remove("template-1")

        assert service.find("template-1") is None

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError):
            service.remove("template-1")

    def test_replace_template(self):
        service, _ = _build_service()

        service.register(_template("template-1", binding_ids=("binding-1",)))

        replacement = _template("template-1", name="renamed", binding_ids=("binding-1", "binding-2"))
        service.replace(replacement)

        assert service.find("template-1") == replacement

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError):
            service.replace(_template("template-unknown"))

    def test_instantiate_template_preserves_binding_order(self):
        service, _ = _build_service()

        service.register(
            _template("template-1", binding_ids=("binding-2", "binding-1", "binding-3"))
        )

        instances = service.instantiate("template-1")

        assert isinstance(instances, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection)
        assert [instance.profile_id for instance in instances.bindings] == ["development"] * 3
        assert len(instances.bindings) == 3

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError):
            service.instantiate("template-unknown")

    def test_instantiate_produces_independent_instances(self):
        service, _ = _build_service()

        service.register(_template("template-1", binding_ids=("binding-1", "binding-2")))

        first_run = service.instantiate("template-1")
        second_run = service.instantiate("template-1")

        first_ids = {instance.binding_id for instance in first_run.bindings}
        second_ids = {instance.binding_id for instance in second_run.bindings}

        assert first_ids.isdisjoint(second_ids)

        for original_id, instance in zip(("binding-1", "binding-2"), first_run.bindings):
            assert instance.binding_id != original_id
            assert instance.profile_id == "development"
            assert instance.capability_id == "capability-a"

    def test_lookup_and_list(self):
        service, _ = _build_service()

        first = service.register(_template("template-1", binding_ids=("binding-1",)))
        second = service.register(_template("template-2", binding_ids=("binding-2",)))

        assert service.find("template-1") == first
        assert service.find("template-missing") is None

        collection = service.list()

        assert isinstance(collection, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCollection)
        assert collection.templates == (first, second)

    def test_duplicate_template_id_rejection(self):
        service, _ = _build_service()

        service.register(_template("template-1", binding_ids=("binding-1",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError):
            service.register(_template("template-1", binding_ids=("binding-2",)))

    def test_reject_invalid_templates(self):
        service, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError):
            service.register(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError):
            _template("   ", binding_ids=("binding-1",))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError):
            service.register(_template("template-1", binding_ids=("binding-unknown",)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError):
            service.find("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError):
            service.remove("   ")

    def test_immutable_collections(self):
        service, _ = _build_service()

        service.register(_template("template-1", binding_ids=("binding-1",)))

        collection = service.list()

        with pytest.raises(AttributeError):
            collection.templates = ()

        template = collection.templates[0]

        with pytest.raises(AttributeError):
            template.name = "renamed"
