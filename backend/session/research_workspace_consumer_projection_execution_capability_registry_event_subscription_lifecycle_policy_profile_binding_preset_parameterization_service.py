from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_parameter_values import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterValues,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_parameterization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService:
    """
    Validates, defaults, and applies configurable parameters for a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding preset, so one
    preset can generate multiple binding configurations.

    The service's responsibility is parameter handling and
    delegating to the underlying preset service for instantiation,
    not preset registration, resolution, or validation of a preset's
    own fields. It does NOT register presets, resolve presets,
    validate a preset's own fields, persist results, log, or publish
    events. A preset carries no parameter-driven fields of its own,
    so instantiation always produces the same independent binding
    sets a plain preset instantiation would; parameter values are
    validated and defaulted, not substituted into the produced
    bindings.

    The service is:
    - Stateless: No mutable instance state; the preset service and
      parameter definitions it was constructed with are treated as
      read-only
    - Deterministic: Same preset ID, parameter definitions, and
      supplied values always produce the same outcome
    - Side-effect free: Never mutates its inputs
    - Order-preserving: Merged values follow the declared parameter
      order, not the order values were supplied in
    """

    def __init__(self, preset_service, parameter_definitions):
        """
        Args:
            preset_service: The service used to look up a preset and
                instantiate its independent binding sets. Any object
                exposing `find(preset_id)` and `instantiate(preset_id)`
                is accepted
            parameter_definitions: An immutable mapping of preset ID
                to the tuple of parameters that preset exposes. A
                preset ID absent from the mapping is treated as
                declaring no parameters

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError:
                If the preset service or parameter definitions is
                None
        """

        if preset_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError(
                "Cannot initialize a parameterization service with a None preset service."
            )

        if parameter_definitions is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError(
                "Cannot initialize a parameterization service with None parameter definitions."
            )

        self._preset_service = preset_service
        self._parameter_definitions = parameter_definitions

    def validate(
        self,
        preset_id: str,
        values,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterValues:
        """
        Validate supplied parameter values against a preset's
        declared parameters, applying default values for any
        parameter that was omitted.

        Args:
            preset_id: The identifier of the preset to validate
                against
            values: The supplied parameter values

        Returns:
            An immutable, fully merged set of parameter values, with
            every parameter's default applied where a value was
            omitted, in declared parameter order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError:
                If the preset ID is None or blank, its declared
                parameters contain duplicate names, values is None,
                values contains a name not declared for the preset, a
                supplied value's type does not match its parameter's
                declared type, or a required parameter has no
                supplied value and no default
        """

        parameters = self._validated_parameters(preset_id)

        if values is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError(
                "Cannot validate None parameter values."
            )

        supplied = values.values
        known_names = {parameter.name for parameter in parameters}

        for name in supplied:
            if name not in known_names:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError(
                    f"Cannot validate parameter values: {name!r} is not a supported "
                    f"parameter of preset ID {preset_id!r}."
                )

        merged = {}

        for parameter in parameters:
            if parameter.name in supplied:
                value = supplied[parameter.name]

                if parameter.type is not None and not isinstance(value, parameter.type):
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError(
                        f"Cannot validate parameter {parameter.name!r}: expected a value "
                        f"of type {parameter.type.__name__!r}."
                    )

                merged[parameter.name] = value
            elif parameter.default_value is not None:
                merged[parameter.name] = parameter.default_value
            elif parameter.required:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError(
                    f"Cannot validate parameter values: required parameter "
                    f"{parameter.name!r} has no supplied value and no default."
                )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterValues(
            values=MappingProxyType(merged),
        )

    def defaults(
        self,
        preset_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterValues:
        """
        Read the default values declared by a preset's parameters.

        Args:
            preset_id: The identifier of the preset to read defaults
                from

        Returns:
            An immutable set of every parameter's default value, in
            declared parameter order, omitting parameters with no
            default

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError:
                If the preset ID is None or blank, or its declared
                parameters contain duplicate names
        """

        parameters = self._validated_parameters(preset_id)

        merged = {
            parameter.name: parameter.default_value
            for parameter in parameters
            if parameter.default_value is not None
        }

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterValues(
            values=MappingProxyType(merged),
        )

    def instantiate(self, preset_id: str, values):
        """
        Validate a set of parameter values against a preset, then
        instantiate the preset's independent binding sets.

        Args:
            preset_id: The identifier of the preset to instantiate
            values: The parameter values to validate before
                instantiation

        Returns:
            The independent binding collections produced by the
            underlying preset service

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError:
                If the parameter values are invalid, as described by
                validate()
        """

        self.validate(preset_id, values)

        return self._preset_service.instantiate(preset_id)

    def supported_parameters(self, preset_id: str) -> tuple:
        """
        List the parameters a preset declares, in declared order.

        Returns:
            An immutable tuple of the preset's declared parameters,
            or an empty tuple if the preset declares none

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError:
                If the preset ID is None or blank, or its declared
                parameters contain duplicate names
        """

        return self._validated_parameters(preset_id)

    def _validated_parameters(self, preset_id: str) -> tuple:
        self._validate_preset_id(preset_id)

        parameters = tuple(self._parameter_definitions.get(preset_id, ()))

        seen_names = set()

        for parameter in parameters:
            if parameter.name in seen_names:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError(
                    f"Cannot operate on preset ID {preset_id!r}: duplicate parameter "
                    f"name {parameter.name!r} declared."
                )

            seen_names.add(parameter.name)

        return parameters

    def _validate_preset_id(self, preset_id: str) -> None:
        if preset_id is None or not preset_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationError(
                "Cannot operate on a binding preset with an empty or blank preset ID."
            )
