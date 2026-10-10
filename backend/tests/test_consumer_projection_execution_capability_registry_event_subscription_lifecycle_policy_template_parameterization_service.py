import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterSet,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterValues,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService,
)


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        ),
        initial_state,
    )


def _build_template():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
        template_id="standard-registration",

        template_name="Standard Registration",

        description="A standard registration lifecycle policy.",

        lifecycle_policy=_build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        ),
    )


def _build_parameter(name, type_=str, required=False, default_value=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameter(
        name=name,

        type=type_,

        required=required,

        default_value=default_value,
    )


def _build_values(**values):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterValues(
        values=values,
    )


class TestApplyDefaults:
    """Omitted parameters are filled in from the parameter set's defaults."""

    def test_apply_defaults(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterSet(
            parameters=(
                _build_parameter(
                    "retry_limit",

                    type_=int,

                    default_value=3,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        merged = service.validate(
            parameter_set,

            _build_values(),
        )

        assert isinstance(
            merged,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterValues,
        )
        assert dict(merged.values) == {"retry_limit": 3}

        default_values = service.defaults(
            parameter_set
        )

        assert dict(default_values.values) == {"retry_limit": 3}


class TestOverrideDefaults:
    """A supplied value overrides a parameter's default."""

    def test_override_defaults(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterSet(
            parameters=(
                _build_parameter(
                    "retry_limit",

                    type_=int,

                    default_value=3,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        merged = service.validate(
            parameter_set,

            _build_values(
                retry_limit=7,
            ),
        )

        assert dict(merged.values) == {"retry_limit": 7}


class TestRequiredParameterValidation:
    """A required parameter with no value and no default is rejected."""

    def test_required_parameter_validation(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterSet(
            parameters=(
                _build_parameter(
                    "region",

                    required=True,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError
        ):
            service.validate(
                parameter_set,

                _build_values(),
            )

        merged = service.validate(
            parameter_set,

            _build_values(
                region="us-east-1",
            ),
        )

        assert dict(merged.values) == {"region": "us-east-1"}


class TestUnknownParameterRejection:
    """A supplied value for an undeclared parameter is rejected."""

    def test_unknown_parameter_rejection(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterSet(
            parameters=(
                _build_parameter(
                    "retry_limit",

                    type_=int,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError
        ):
            service.validate(
                parameter_set,

                _build_values(
                    unexpected="value",
                ),
            )


class TestDuplicateParameterRejection:
    """A parameter set with duplicate parameter names is rejected."""

    def test_duplicate_parameter_rejection(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterSet(
            parameters=(
                _build_parameter("retry_limit"),
                _build_parameter("retry_limit"),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError
        ):
            service.validate(
                parameter_set,

                _build_values(),
            )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError
        ):
            service.defaults(
                parameter_set
            )


class TestTypeValidation:
    """A supplied value of the wrong type is rejected."""

    def test_type_validation(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterSet(
            parameters=(
                _build_parameter(
                    "retry_limit",

                    type_=int,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError
        ):
            service.validate(
                parameter_set,

                _build_values(
                    retry_limit="not-an-int",
                ),
            )


class TestApply:
    """apply() returns a new, independent lifecycle policy instance."""

    def test_apply(self):
        template = _build_template()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        result = service.apply(
            template,

            _build_values(),
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
        )
        assert result == template.lifecycle_policy
        assert result is not template.lifecycle_policy


class TestImmutableTemplate:
    """apply() never mutates the template it reads from."""

    def test_immutable_template(self):
        template = _build_template()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        service.apply(
            template,

            _build_values(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            template.template_id = "changed"


class TestImmutableParameterSet:
    """A parameter set and its parameters cannot be reassigned."""

    def test_immutable_parameter_set(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterSet(
            parameters=(
                _build_parameter("retry_limit"),
            ),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            parameter_set.parameters = ()

        with pytest.raises(dataclasses.FrozenInstanceError):
            parameter_set.parameters[0].name = "changed"


class TestRejectNoneInputs:
    """None parameter sets, values, and templates are rejected."""

    def test_reject_none_parameter_set(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError
        ):
            service.validate(
                None,

                _build_values(),
            )

    def test_reject_none_values(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterSet(
            parameters=(),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError
        ):
            service.validate(
                parameter_set,

                None,
            )

    def test_reject_none_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError
        ):
            service.apply(
                None,

                _build_values(),
            )

    def test_reject_none_defaults_parameter_set(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError
        ):
            service.defaults(
                None
            )
