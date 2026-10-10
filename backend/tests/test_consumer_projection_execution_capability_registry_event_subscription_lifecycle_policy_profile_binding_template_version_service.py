import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService,
)


def _template(template_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=binding_ids,
        metadata={},
    )


def _parameter(name, type_=str, required=False, default_value=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameter(
        name=name,
        type=type_,
        required=required,
        default_value=default_value,
    )


def _build_service(templates=(("template-1", ("binding-1", "binding-2")),), parameter_definitions=None):
    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()

    for template_id, binding_ids in templates:
        template_registry.register(_template(template_id, binding_ids=binding_ids))

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService(
        template_registry,
        parameter_definitions or {},
    )

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService(
        template_registry,
        parameterization_service,
    )

    return service, template_registry, parameterization_service


class TestPublishVersion:
    def test_publish_version(self):
        parameters = (_parameter("retry_limit", type_=int, default_value=3),)
        service, _, _ = _build_service(parameter_definitions={"template-1": parameters})

        version = service.publish("template-1", "v1")

        assert isinstance(version, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion)
        assert version.version == "v1"
        assert version.binding_ids == ("binding-1", "binding-2")
        assert version.parameters == parameters
        assert version.created_at is not None

    def test_publish_multiple_versions(self):
        service, template_registry, _ = _build_service()

        service.publish("template-1", "v1")

        template_registry.replace(_template("template-1", binding_ids=("binding-1",)))
        service.publish("template-1", "v2")

        history = service.history("template-1")

        assert [v.version for v in history.versions] == ["v1", "v2"]
        assert history.current_version == "v2"

    def test_reject_duplicate_version(self):
        service, _, _ = _build_service()

        service.publish("template-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            service.publish("template-1", "v1")

    def test_reject_unknown_template(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            service.publish("template-missing", "v1")

    def test_reject_blank_identifiers(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            service.publish("   ", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            service.publish("template-1", None)


class TestLatestLookup:
    def test_latest_lookup(self):
        service, template_registry, _ = _build_service()

        service.publish("template-1", "v1")
        template_registry.replace(_template("template-1", binding_ids=("binding-2",)))
        second = service.publish("template-1", "v2")

        assert service.latest("template-1") == second

    def test_latest_unknown_template_raises(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            service.latest("template-missing")


class TestFindVersion:
    def test_find_existing_version(self):
        service, _, _ = _build_service()

        published = service.publish("template-1", "v1")

        assert service.find("template-1", "v1") == published

    def test_find_missing_version_returns_none(self):
        service, _, _ = _build_service()

        service.publish("template-1", "v1")

        assert service.find("template-1", "v-missing") is None

    def test_find_unknown_template_returns_none(self):
        service, _, _ = _build_service()

        assert service.find("template-missing", "v1") is None


class TestVersionHistory:
    def test_history(self):
        service, _, _ = _build_service()

        first = service.publish("template-1", "v1")
        second = service.publish("template-1", "v2")

        history = service.history("template-1")

        assert isinstance(history, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionHistory)
        assert history.template_id == "template-1"
        assert history.current_version == "v2"
        assert history.versions == (first, second)

    def test_history_unknown_template_raises(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            service.history("template-missing")


class TestRollback:
    def test_rollback_creates_new_current_version(self):
        parameters = (_parameter("retry_limit", type_=int, default_value=3),)
        service, template_registry, _ = _build_service(parameter_definitions={"template-1": parameters})

        first = service.publish("template-1", "v1")
        template_registry.replace(_template("template-1", binding_ids=("binding-2",)))
        service.publish("template-1", "v2")

        restored = service.rollback("template-1", "v1")

        assert restored.version != "v1"
        assert restored.version != "v2"
        assert restored.binding_ids == first.binding_ids
        assert restored.parameters == first.parameters

        history = service.history("template-1")

        assert history.current_version == restored.version
        assert [v.version for v in history.versions] == ["v1", "v2", restored.version]

    def test_rollback_unknown_version_raises(self):
        service, _, _ = _build_service()

        service.publish("template-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            service.rollback("template-1", "v-missing")

    def test_rollback_unknown_template_raises(self):
        service, _, _ = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            service.rollback("template-missing", "v1")

    def test_reject_blank_identifiers(self):
        service, _, _ = _build_service()

        service.publish("template-1", "v1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            service.rollback("template-1", "   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            service.rollback(None, "v1")


class TestImmutableHistory:
    def test_immutable_history(self):
        service, _, _ = _build_service()

        service.publish("template-1", "v1")

        history = service.history("template-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            history.current_version = "v-changed"

    def test_immutable_version(self):
        service, _, _ = _build_service()

        version = service.publish("template-1", "v1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            version.version = "v-changed"

    def test_does_not_mutate_prior_versions_on_rollback(self):
        service, template_registry, _ = _build_service()

        first = service.publish("template-1", "v1")
        template_registry.replace(_template("template-1", binding_ids=("binding-2",)))
        service.publish("template-1", "v2")

        service.rollback("template-1", "v1")

        assert service.find("template-1", "v1") == first


class TestRejectNoneDependencies:
    def test_reject_none_dependencies(self):
        _, template_registry, parameterization_service = _build_service()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService(
                None, parameterization_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService(
                template_registry, None
            )
