from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_parameter_values import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterValues,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_parameterization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService:
    """
    Validates, defaults, and applies configurable parameters for a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding template, so one
    template can generate multiple binding variants.

    The service's responsibility is parameter handling and
    delegating to the underlying template service for instantiation,
    not template registration, resolution, or validation of a
    template's own fields. It does NOT register templates, resolve
    templates, validate a template's own fields, persist results,
    log, or publish events. A binding carries no parameter-driven
    fields of its own, so instantiation always produces the same
    independent binding copies a plain template instantiation would;
    parameter values are validated and defaulted, not substituted
    into the produced bindings.

    The service is:
    - Stateless: No mutable instance state; the template service and
      parameter definitions it was constructed with are treated as
      read-only
    - Deterministic: Same template ID, parameter definitions, and
      supplied values always produce the same outcome
    - Side-effect free: Never mutates its inputs
    - Order-preserving: Merged values follow the declared parameter
      order, not the order values were supplied in
    """

    def __init__(self, template_service, parameter_definitions):
        """
        Args:
            template_service: The service used to look up a template
                and instantiate its independent binding copies. Any
                object exposing `find(template_id)` and
                `instantiate(template_id)` is accepted
            parameter_definitions: An immutable mapping of template ID
                to the tuple of parameters that template exposes. A
                template ID absent from the mapping is treated as
                declaring no parameters

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError:
                If the template service or parameter definitions is
                None
        """

        if template_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError(
                "Cannot initialize a parameterization service with a None template service."
            )

        if parameter_definitions is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError(
                "Cannot initialize a parameterization service with None parameter definitions."
            )

        self._template_service = template_service
        self._parameter_definitions = parameter_definitions

    def validate(
        self,
        template_id: str,
        values,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterValues:
        """
        Validate supplied parameter values against a template's
        declared parameters, applying default values for any
        parameter that was omitted.

        Args:
            template_id: The identifier of the template to validate
                against
            values: The supplied parameter values

        Returns:
            An immutable, fully merged set of parameter values, with
            every parameter's default applied where a value was
            omitted, in declared parameter order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError:
                If the template ID is None or blank, its declared
                parameters contain duplicate names, values is None,
                values contains a name not declared for the template,
                a supplied value's type does not match its
                parameter's declared type, or a required parameter
                has no supplied value and no default
        """

        parameters = self._validated_parameters(template_id)

        if values is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError(
                "Cannot validate None parameter values."
            )

        supplied = values.values
        known_names = {parameter.name for parameter in parameters}

        for name in supplied:
            if name not in known_names:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError(
                    f"Cannot validate parameter values: {name!r} is not a supported "
                    f"parameter of template ID {template_id!r}."
                )

        merged = {}

        for parameter in parameters:
            if parameter.name in supplied:
                value = supplied[parameter.name]

                if parameter.type is not None and not isinstance(value, parameter.type):
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError(
                        f"Cannot validate parameter {parameter.name!r}: expected a value "
                        f"of type {parameter.type.__name__!r}."
                    )

                merged[parameter.name] = value
            elif parameter.default_value is not None:
                merged[parameter.name] = parameter.default_value
            elif parameter.required:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError(
                    f"Cannot validate parameter values: required parameter "
                    f"{parameter.name!r} has no supplied value and no default."
                )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterValues(
            values=MappingProxyType(merged),
        )

    def defaults(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterValues:
        """
        Read the default values declared by a template's parameters.

        Args:
            template_id: The identifier of the template to read
                defaults from

        Returns:
            An immutable set of every parameter's default value, in
            declared parameter order, omitting parameters with no
            default

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError:
                If the template ID is None or blank, or its declared
                parameters contain duplicate names
        """

        parameters = self._validated_parameters(template_id)

        merged = {
            parameter.name: parameter.default_value
            for parameter in parameters
            if parameter.default_value is not None
        }

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterValues(
            values=MappingProxyType(merged),
        )

    def instantiate(self, template_id: str, values):
        """
        Validate a set of parameter values against a template, then
        instantiate the template's independent binding copies.

        Args:
            template_id: The identifier of the template to instantiate
            values: The parameter values to validate before
                instantiation

        Returns:
            The independent binding copies produced by the underlying
            template service

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError:
                If the parameter values are invalid, as described by
                validate()
        """

        self.validate(template_id, values)

        return self._template_service.instantiate(template_id)

    def supported_parameters(self, template_id: str) -> tuple:
        """
        List the parameters a template declares, in declared order.

        Returns:
            An immutable tuple of the template's declared parameters,
            or an empty tuple if the template declares none

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError:
                If the template ID is None or blank, or its declared
                parameters contain duplicate names
        """

        return self._validated_parameters(template_id)

    def _validated_parameters(self, template_id: str) -> tuple:
        self._validate_template_id(template_id)

        parameters = tuple(self._parameter_definitions.get(template_id, ()))

        seen_names = set()

        for parameter in parameters:
            if parameter.name in seen_names:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError(
                    f"Cannot operate on template ID {template_id!r}: duplicate parameter "
                    f"name {parameter.name!r} declared."
                )

            seen_names.add(parameter.name)

        return parameters

    def _validate_template_id(self, template_id: str) -> None:
        if template_id is None or not template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationError(
                "Cannot operate on a binding template with an empty or blank template ID."
            )
