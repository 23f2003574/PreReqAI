from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_parameter_values import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterValues,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_parameterization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError,
)


SUPPORTED_PARAMETER_TYPES = (

    str,

    int,

    float,

    bool,

    list,

    dict,

    tuple,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationService:
    """
    Defines, validates, defaults, and applies configurable
    parameters for a consumer projection execution capability
    registry event subscription lifecycle policy profile, so
    multiple profile configurations can be produced from the same
    underlying profile without modifying it.

    The service's responsibility is parameter handling, not profile
    registration, resolution, or validation of the profile itself.
    It does NOT register profiles, resolve profiles, validate a
    profile's own fields, persist results, log, or publish events.

    The service is:
    - Stateless: No instance state
    - Deterministic: Same parameter set, values, and profile always
      produce the same outcome
    - Side-effect free: Never mutates its inputs
    - Order-preserving: Merged values follow the parameter set's
      declared parameter order, not the order values were supplied
      in
    """

    def define(

        self,

        parameter_set,

    ) -> tuple:
        """
        Validate a parameter set's own well-formedness.

        Args:
            parameter_set: The parameter set to define

        Returns:
            An immutable tuple of every parameter in the set,
            preserving declared order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError:
                If the parameter set is None, contains a parameter
                with a blank parameter name, contains duplicate
                parameter names, or declares an unsupported
                parameter type
        """

        return self._validated_parameters(
            parameter_set
        )

    def validate(

        self,

        parameter_set,

        parameter_values,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterValues:
        """
        Validate supplied parameter values against a parameter set,
        applying default values for any parameter that was omitted.

        Args:
            parameter_set: The parameter set to validate against
            parameter_values: The supplied parameter values

        Returns:
            An immutable, fully merged set of parameter values, with
            every parameter's default applied where a value was
            omitted, in parameter set order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError:
                If the parameter set or parameter values is None, the
                parameter set is malformed, parameter_values contains
                a name not defined in the parameter set, a supplied
                value's type is incompatible with its parameter's
                declared type, or a required parameter has no
                supplied value and no default
        """

        parameters = self._validated_parameters(
            parameter_set
        )

        if parameter_values is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                    "Cannot validate None parameter values."
                )
            )

        supplied = parameter_values.values

        known_names = {

            parameter.parameter_name

            for parameter

            in parameters
        }

        for name in supplied:

            if name not in known_names:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                        f"Cannot validate parameter values: {name!r} is not "
                        "defined in the parameter set."
                    )
                )

        merged = {}

        for parameter in parameters:

            if parameter.parameter_name in supplied:

                value = supplied[parameter.parameter_name]

                if (

                    parameter.parameter_type is not None

                    and not isinstance(
                        value,
                        parameter.parameter_type,
                    )
                ):

                    raise (
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                            "Cannot validate parameter "
                            f"{parameter.parameter_name!r}: expected a "
                            f"value of type "
                            f"{parameter.parameter_type.__name__!r}."
                        )
                    )

                merged[parameter.parameter_name] = value

            elif parameter.default_value is not None:

                merged[parameter.parameter_name] = parameter.default_value

            elif parameter.required:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                        "Cannot validate parameter values: required "
                        f"parameter {parameter.parameter_name!r} has no "
                        "supplied value and no default."
                    )
                )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterValues(
                values=MappingProxyType(
                    merged
                )
            )
        )

    def defaults(

        self,

        parameter_set,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterValues:
        """
        Read the default values declared by a parameter set.

        Args:
            parameter_set: The parameter set to read defaults from

        Returns:
            An immutable set of every parameter's default value, in
            parameter set order, omitting parameters with no default

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError:
                If the parameter set is None or malformed
        """

        parameters = self._validated_parameters(
            parameter_set
        )

        merged = {

            parameter.parameter_name: parameter.default_value

            for parameter

            in parameters

            if parameter.default_value is not None
        }

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterValues(
                values=MappingProxyType(
                    merged
                )
            )
        )

    def apply(

        self,

        profile,

        parameter_values,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance:
        """
        Apply a set of parameter values to a profile, producing a
        new, independent profile instance.

        Args:
            profile: The profile to apply values to
            parameter_values: The parameter values to apply,
                typically the result of validate()

        Returns:
            A new profile instance, independent of the profile's
            own definition

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError:
                If the profile is None, the profile has a missing
                policy identifier collection, or the parameter
                values are None
        """

        if profile is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                    "Cannot apply parameter values to a None profile."
                )
            )

        if profile.policy_identifiers is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                    "Cannot apply parameter values to a profile with a "
                    "missing policy identifier collection."
                )
            )

        if parameter_values is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                    "Cannot apply None parameter values."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance(
                profile_id=profile.profile_id,

                version=None,

                policy_identifiers=tuple(
                    profile.policy_identifiers
                ),

                parameter_values=MappingProxyType(
                    dict(
                        parameter_values.values
                    )
                ),
            )
        )

    def _validated_parameters(

        self,

        parameter_set,

    ) -> tuple:

        if parameter_set is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                    "Cannot operate on a None parameter set."
                )
            )

        parameters = parameter_set.parameters

        seen_names = set()

        for parameter in parameters:

            if (

                parameter.parameter_name is None

                or not parameter.parameter_name.strip()
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                        "Cannot operate on a parameter set containing a "
                        "parameter with an empty or blank parameter name."
                    )
                )

            if parameter.parameter_name in seen_names:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                        "Cannot operate on a parameter set with duplicate "
                        f"parameter name {parameter.parameter_name!r}."
                    )
                )

            seen_names.add(
                parameter.parameter_name
            )

            if (

                parameter.parameter_type is not None

                and parameter.parameter_type not in SUPPORTED_PARAMETER_TYPES
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileParameterizationError(
                        f"Cannot operate on parameter {parameter.parameter_name!r}: "
                        f"unsupported parameter type "
                        f"{parameter.parameter_type!r}."
                    )
                )

        return parameters
