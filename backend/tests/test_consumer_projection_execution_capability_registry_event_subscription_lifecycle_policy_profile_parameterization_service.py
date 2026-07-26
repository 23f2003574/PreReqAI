import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterValues,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService,
)


def _build_profile(profile_id="development", policy_identifiers=("policy-a",)):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,

        profile_name=profile_id,

        description=f"Profile {profile_id}.",

        policy_identifiers=policy_identifiers,
    )


def _build_parameter(name, type_=str, required=False, default_value=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameter(
        parameter_name=name,

        parameter_type=type_,

        required=required,

        default_value=default_value,
    )


def _build_values(**values):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterValues(
        values=values,
    )


class TestDefineParameterSet:
    """define() validates a well-formed parameter set and returns its parameters."""

    def test_define_parameter_set(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(
                _build_parameter(
                    "retry_limit",

                    type_=int,

                    default_value=3,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        defined = service.define(
            parameter_set
        )

        assert defined == parameter_set.parameters


class TestApplyDefaults:
    """Omitted parameters are filled in from the parameter set's defaults."""

    def test_apply_defaults(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(
                _build_parameter(
                    "retry_limit",

                    type_=int,

                    default_value=3,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        merged = service.validate(
            parameter_set,

            _build_values(),
        )

        assert isinstance(
            merged,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterValues,
        )
        assert dict(merged.values) == {"retry_limit": 3}

        default_values = service.defaults(
            parameter_set
        )

        assert dict(default_values.values) == {"retry_limit": 3}


class TestApplyExplicitValues:
    """A supplied value overrides a parameter's default."""

    def test_apply_explicit_values(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(
                _build_parameter(
                    "retry_limit",

                    type_=int,

                    default_value=3,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

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
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(
                _build_parameter(
                    "region",

                    required=True,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
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


class TestTypeValidation:
    """A supplied value of an incompatible type is rejected."""

    def test_type_validation(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(
                _build_parameter(
                    "retry_limit",

                    type_=int,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.validate(
                parameter_set,

                _build_values(
                    retry_limit="not-an-int",
                ),
            )


class TestUnknownParameterRejection:
    """A supplied value for an undeclared parameter is rejected."""

    def test_unknown_parameter_rejection(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(
                _build_parameter(
                    "retry_limit",

                    type_=int,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
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
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(
                _build_parameter("retry_limit"),
                _build_parameter("retry_limit"),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.define(
                parameter_set
            )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.validate(
                parameter_set,

                _build_values(),
            )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.defaults(
                parameter_set
            )


class TestBlankParameterNameRejection:
    """A parameter set containing a blank parameter name is rejected."""

    def test_blank_parameter_name_rejection(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(
                _build_parameter("   "),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.define(
                parameter_set
            )


class TestUnsupportedParameterTypeRejection:
    """A parameter set declaring an unsupported parameter type is rejected."""

    def test_unsupported_parameter_type_rejection(self):
        class Unsupported:
            pass

        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(
                _build_parameter(
                    "custom",

                    type_=Unsupported,
                ),
            ),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.define(
                parameter_set
            )


class TestApply:
    """apply() returns a new, independent profile instance."""

    def test_apply(self):
        profile = _build_profile()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        result = service.apply(
            profile,

            _build_values(
                retry_limit=3,
            ),
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
        )
        assert result.profile_id == profile.profile_id
        assert result.policy_identifiers == profile.policy_identifiers
        assert dict(result.parameter_values) == {"retry_limit": 3}


class TestImmutableProfile:
    """apply() never mutates the profile it reads from."""

    def test_immutable_profile(self):
        profile = _build_profile()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        service.apply(
            profile,

            _build_values(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            profile.profile_id = "changed"


class TestImmutableParameterSet:
    """A parameter set and its parameters cannot be reassigned."""

    def test_immutable_parameter_set(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(
                _build_parameter("retry_limit"),
            ),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            parameter_set.parameters = ()

        with pytest.raises(dataclasses.FrozenInstanceError):
            parameter_set.parameters[0].parameter_name = "changed"


class TestImmutableParameterValues:
    """A parameter values object cannot have its fields reassigned."""

    def test_immutable_parameter_values(self):
        values = _build_values(
            retry_limit=3,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            values.values = {}


class TestRejectNoneInputs:
    """None parameter sets, values, and profiles are rejected."""

    def test_reject_none_parameter_set(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.validate(
                None,

                _build_values(),
            )

    def test_reject_none_define_parameter_set(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.define(
                None
            )

    def test_reject_none_values(self):
        parameter_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterSet(
            parameters=(),
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.validate(
                parameter_set,

                None,
            )

    def test_reject_none_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.apply(
                None,

                _build_values(),
            )

    def test_reject_none_apply_values(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.apply(
                _build_profile(),

                None,
            )

    def test_reject_none_defaults_parameter_set(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError
        ):
            service.defaults(
                None
            )
