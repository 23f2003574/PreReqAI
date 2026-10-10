import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterValues,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
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
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameter(
        name=name,
        type=type_,
        required=required,
        default_value=default_value,
    )


def _values(**values):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterValues(
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

    preset_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetService(template_service)
    preset_service.register(
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
            preset_id="preset-1",
            name="Preset One",
            description="A preset.",
            binding_template_ids=("template-1",),
        )
    )

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService(
        preset_service,
        parameter_definitions or {},
    )

    return parameterization_service, preset_service


class TestInstantiateWithDefaults:
    def test_instantiate_with_defaults(self):
        service, _ = _build_context(
            parameter_definitions={"preset-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        merged = service.validate("preset-1", _values())

        assert isinstance(merged, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterValues)
        assert dict(merged.values) == {"retry_limit": 3}
        assert dict(service.defaults("preset-1").values) == {"retry_limit": 3}

        instances = service.instantiate("preset-1", _values())

        assert isinstance(instances, tuple)
        assert len(instances) == 1
        assert isinstance(instances[0], ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection)
        assert len(instances[0].bindings) == 2


class TestOverrideDefaults:
    def test_override_defaults(self):
        service, _ = _build_context(
            parameter_definitions={"preset-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        merged = service.validate("preset-1", _values(retry_limit=7))

        assert dict(merged.values) == {"retry_limit": 7}


class TestRequiredParameterValidation:
    def test_required_parameter_validation(self):
        service, _ = _build_context(
            parameter_definitions={"preset-1": (_parameter("region", required=True),)},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            service.validate("preset-1", _values())

        merged = service.validate("preset-1", _values(region="us-east-1"))

        assert dict(merged.values) == {"region": "us-east-1"}


class TestInvalidTypeRejection:
    def test_invalid_type_rejection(self):
        service, _ = _build_context(
            parameter_definitions={"preset-1": (_parameter("retry_limit", type_=int),)},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            service.validate("preset-1", _values(retry_limit="not-an-int"))


class TestUnknownParameterRejection:
    def test_unknown_parameter_rejection(self):
        service, _ = _build_context(
            parameter_definitions={"preset-1": (_parameter("retry_limit", type_=int),)},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            service.validate("preset-1", _values(unexpected="value"))


class TestDuplicateParameterRejection:
    def test_duplicate_parameter_rejection(self):
        service, _ = _build_context(
            parameter_definitions={
                "preset-1": (_parameter("retry_limit"), _parameter("retry_limit")),
            },
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            service.validate("preset-1", _values())

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            service.defaults("preset-1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            service.supported_parameters("preset-1")


class TestSupportedParameters:
    def test_supported_parameters(self):
        parameters = (_parameter("retry_limit", type_=int, default_value=3),)
        service, _ = _build_context(parameter_definitions={"preset-1": parameters})

        assert service.supported_parameters("preset-1") == parameters

    def test_undeclared_preset_has_no_parameters(self):
        service, _ = _build_context()

        assert service.supported_parameters("preset-1") == ()


class TestImmutableInstantiatedBindings:
    def test_immutable_instantiated_bindings(self):
        service, _ = _build_context(
            parameter_definitions={"preset-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        instances = service.instantiate("preset-1", _values())

        with pytest.raises(dataclasses.FrozenInstanceError):
            instances[0].bindings[0].binding_id = "changed"

        with pytest.raises(dataclasses.FrozenInstanceError):
            instances[0].bindings = ()

    def test_instantiate_produces_independent_copies(self):
        service, _ = _build_context(
            parameter_definitions={"preset-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        first_run = service.instantiate("preset-1", _values())
        second_run = service.instantiate("preset-1", _values())

        first_ids = {instance.binding_id for collection in first_run for instance in collection.bindings}
        second_ids = {instance.binding_id for collection in second_run for instance in collection.bindings}

        assert first_ids.isdisjoint(second_ids)


class TestRejectInvalidInputs:
    def test_reject_none_dependencies(self):
        _, preset_service = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService(None, {})

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService(preset_service, None)

    def test_reject_blank_preset_id(self):
        service, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            service.validate("   ", _values())

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            service.defaults(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            service.supported_parameters("")

    def test_reject_none_values(self):
        service, _ = _build_context(
            parameter_definitions={"preset-1": ()},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError):
            service.validate("preset-1", None)
