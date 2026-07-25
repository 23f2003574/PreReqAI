from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_parameter_values import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterValues,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_parameterization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationService:
    """
    Validates, defaults, and applies configurable parameters for a
    consumer projection execution capability registry event
    subscription lifecycle policy template, so multiple policy
    variants can be instantiated from the same template.

    The service's responsibility is parameter handling, not template
    registration, resolution, or validation of the template itself.
    It does NOT register templates, resolve templates, validate a
    template's own fields, persist results, log, or publish events.

    The service is:
    - Stateless: No instance state
    - Deterministic: Same parameter set, values, and template always
      produce the same outcome
    - Side-effect free: Never mutates its inputs
    - Order-preserving: Merged values follow the parameter set's
      declared parameter order, not the order values were supplied
      in
    """

    def validate(

        self,

        parameter_set,

        values,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterValues:
        """
        Validate supplied parameter values against a parameter set,
        applying default values for any parameter that was omitted.

        Args:
            parameter_set: The parameter set to validate against
            values: The supplied parameter values

        Returns:
            An immutable, fully merged set of parameter values,
            with every parameter's default applied where a value was
            omitted, in parameter set order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError:
                If the parameter set or values is None, the
                parameter set contains duplicate parameter names,
                values contains a name not defined in the parameter
                set, a supplied value's type does not match its
                parameter's declared type, or a required parameter
                has no supplied value and no default
        """

        parameters = self._validated_parameters(
            parameter_set
        )

        if values is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError(
                    "Cannot validate None parameter values."
                )
            )

        supplied = values.values

        known_names = {

            parameter.name

            for parameter

            in parameters
        }

        for name in supplied:

            if name not in known_names:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError(
                        f"Cannot validate parameter values: {name!r} is not "
                        "defined in the parameter set."
                    )
                )

        merged = {}

        for parameter in parameters:

            if parameter.name in supplied:

                value = supplied[parameter.name]

                if (

                    parameter.type is not None

                    and not isinstance(
                        value,
                        parameter.type,
                    )
                ):

                    raise (
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError(
                            f"Cannot validate parameter {parameter.name!r}: "
                            f"expected a value of type "
                            f"{parameter.type.__name__!r}."
                        )
                    )

                merged[parameter.name] = value

            elif parameter.default_value is not None:

                merged[parameter.name] = parameter.default_value

            elif parameter.required:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError(
                        f"Cannot validate parameter values: required "
                        f"parameter {parameter.name!r} has no supplied "
                        "value and no default."
                    )
                )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterValues(
                values=MappingProxyType(
                    merged
                )
            )
        )

    def defaults(

        self,

        parameter_set,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterValues:
        """
        Read the default values declared by a parameter set.

        Args:
            parameter_set: The parameter set to read defaults from

        Returns:
            An immutable set of every parameter's default value, in
            parameter set order, omitting parameters with no default

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError:
                If the parameter set is None or contains duplicate
                parameter names
        """

        parameters = self._validated_parameters(
            parameter_set
        )

        merged = {

            parameter.name: parameter.default_value

            for parameter

            in parameters

            if parameter.default_value is not None
        }

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterValues(
                values=MappingProxyType(
                    merged
                )
            )
        )

    def apply(

        self,

        template,

        values,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy:
        """
        Apply a set of parameter values to a template, producing a
        new, independent lifecycle policy instance.

        Args:
            template: The template to apply values to
            values: The parameter values to apply, typically the
                result of validate()

        Returns:
            A new lifecycle policy instance, independent of the
            template's own lifecycle policy

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError:
                If the template is None, the template has a missing
                lifecycle policy, or the values are None
        """

        if template is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError(
                    "Cannot apply parameter values to a None template."
                )
            )

        if template.lifecycle_policy is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError(
                    "Cannot apply parameter values to a template with a "
                    "missing lifecycle policy."
                )
            )

        if values is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError(
                    "Cannot apply None parameter values."
                )
            )

        source = template.lifecycle_policy

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy(
                allowed_states=tuple(
                    source.allowed_states
                ),

                initial_state=source.initial_state,
            )
        )

    def _validated_parameters(

        self,

        parameter_set,

    ) -> tuple:

        if parameter_set is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError(
                    "Cannot operate on a None parameter set."
                )
            )

        parameters = parameter_set.parameters

        seen_names = set()

        for parameter in parameters:

            if parameter.name in seen_names:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterizationError(
                        "Cannot operate on a parameter set with duplicate "
                        f"parameter name {parameter.name!r}."
                    )
                )

            seen_names.add(
                parameter.name
            )

        return parameters
