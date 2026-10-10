import dataclasses

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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterValues,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateService,
)


def _binding(binding_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id="development",
        capability_id=f"capability-{binding_id}",
        created_at=datetime.now(timezone.utc),
    )


def _parameter(name, type_=str, required=False, default_value=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameter(
        name=name,
        type=type_,
        required=required,
        default_value=default_value,
    )


def _values(**values):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterValues(
        values=values,
    )


def _build_context(binding_ids=("binding-1", "binding-2"), parameter_definitions=None):
    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()

    for binding_id in binding_ids:
        binding_service.register(_binding(binding_id))

    template_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateService(binding_service)
    template_service.register(
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
            template_id="template-1",
            name="Template One",
            binding_ids=binding_ids,
            metadata={},
        )
    )

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService(
        template_service,
        parameter_definitions or {},
    )

    return parameterization_service, template_service


class TestInstantiateWithDefaults:
    def test_instantiate_with_defaults(self):
        service, _ = _build_context(
            parameter_definitions={"template-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        merged = service.validate("template-1", _values())

        assert isinstance(merged, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterValues)
        assert dict(merged.values) == {"retry_limit": 3}
        assert dict(service.defaults("template-1").values) == {"retry_limit": 3}

        instances = service.instantiate("template-1", _values())

        assert isinstance(instances, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection)
        assert len(instances.bindings) == 2


class TestOverrideDefaults:
    def test_override_defaults(self):
        service, _ = _build_context(
            parameter_definitions={"template-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        merged = service.validate("template-1", _values(retry_limit=7))

        assert dict(merged.values) == {"retry_limit": 7}


class TestRequiredParameterValidation:
    def test_required_parameter_validation(self):
        service, _ = _build_context(
            parameter_definitions={"template-1": (_parameter("region", required=True),)},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            service.validate("template-1", _values())

        merged = service.validate("template-1", _values(region="us-east-1"))

        assert dict(merged.values) == {"region": "us-east-1"}


class TestInvalidTypeRejection:
    def test_invalid_type_rejection(self):
        service, _ = _build_context(
            parameter_definitions={"template-1": (_parameter("retry_limit", type_=int),)},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            service.validate("template-1", _values(retry_limit="not-an-int"))


class TestUnknownParameterRejection:
    def test_unknown_parameter_rejection(self):
        service, _ = _build_context(
            parameter_definitions={"template-1": (_parameter("retry_limit", type_=int),)},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            service.validate("template-1", _values(unexpected="value"))


class TestDuplicateParameterRejection:
    def test_duplicate_parameter_rejection(self):
        service, _ = _build_context(
            parameter_definitions={
                "template-1": (_parameter("retry_limit"), _parameter("retry_limit")),
            },
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            service.validate("template-1", _values())

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            service.defaults("template-1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            service.supported_parameters("template-1")


class TestSupportedParameters:
    def test_supported_parameters(self):
        parameters = (_parameter("retry_limit", type_=int, default_value=3),)
        service, _ = _build_context(parameter_definitions={"template-1": parameters})

        assert service.supported_parameters("template-1") == parameters

    def test_undeclared_template_has_no_parameters(self):
        service, _ = _build_context()

        assert service.supported_parameters("template-1") == ()


class TestImmutableInstantiatedBindings:
    def test_immutable_instantiated_bindings(self):
        service, _ = _build_context(
            parameter_definitions={"template-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        instances = service.instantiate("template-1", _values())

        with pytest.raises(dataclasses.FrozenInstanceError):
            instances.bindings[0].binding_id = "changed"

        with pytest.raises(dataclasses.FrozenInstanceError):
            instances.bindings = ()

    def test_instantiate_produces_independent_copies(self):
        service, _ = _build_context(
            parameter_definitions={"template-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        first_run = service.instantiate("template-1", _values())
        second_run = service.instantiate("template-1", _values())

        first_ids = {instance.binding_id for instance in first_run.bindings}
        second_ids = {instance.binding_id for instance in second_run.bindings}

        assert first_ids.isdisjoint(second_ids)


class TestRejectInvalidInputs:
    def test_reject_none_dependencies(self):
        _, template_service = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService(None, {})

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService(template_service, None)

    def test_reject_blank_template_id(self):
        service, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            service.validate("   ", _values())

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            service.defaults(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            service.supported_parameters("")

    def test_reject_none_values(self):
        service, _ = _build_context(
            parameter_definitions={"template-1": ()},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError):
            service.validate("template-1", None)
