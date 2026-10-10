from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_parameter_values import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterValues,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_parameterization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationService:
    """
    Validates, defaults, and applies configurable parameters for a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace, so one
    workspace can produce multiple deployment-ready configurations.

    The service's responsibility is parameter handling and
    delegating to the underlying workspace service for a configured
    snapshot, not workspace registration, resolution, or validation
    of a workspace's own fields. It does NOT register workspaces,
    resolve workspaces, validate a workspace's own fields, persist
    results, log, or publish events. A workspace carries no
    parameter-driven fields of its own, so applying parameter values
    always produces the same snapshot a plain workspace snapshot
    would; parameter values are validated and defaulted, not
    substituted into the snapshotted workspace.

    The service is:
    - Stateless: No mutable instance state; the workspace service and
      parameter definitions it was constructed with are treated as
      read-only
    - Deterministic: Same workspace ID, parameter definitions, and
      supplied values always produce the same outcome
    - Side-effect free: Never mutates its inputs
    - Order-preserving: Merged values follow the declared parameter
      order, not the order values were supplied in
    """

    def __init__(self, workspace_service, parameter_definitions):
        """
        Args:
            workspace_service: The service used to look up a
                workspace and produce its snapshot. Any object
                exposing `find(workspace_id)` and
                `snapshot(workspace_id)` is accepted
            parameter_definitions: An immutable mapping of workspace
                ID to the tuple of parameters that workspace exposes.
                A workspace ID absent from the mapping is treated as
                declaring no parameters

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError:
                If the workspace service or parameter definitions is
                None
        """

        if workspace_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError(
                "Cannot initialize a parameterization service with a None workspace service."
            )

        if parameter_definitions is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError(
                "Cannot initialize a parameterization service with None parameter definitions."
            )

        self._workspace_service = workspace_service
        self._parameter_definitions = parameter_definitions

    def validate(
        self,
        workspace_id: str,
        values,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterValues:
        """
        Validate supplied parameter values against a workspace's
        declared parameters, applying default values for any
        parameter that was omitted.

        Args:
            workspace_id: The identifier of the workspace to validate
                against
            values: The supplied parameter values

        Returns:
            An immutable, fully merged set of parameter values, with
            every parameter's default applied where a value was
            omitted, in declared parameter order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError:
                If the workspace ID is None or blank, its declared
                parameters contain duplicate names, values is None,
                values contains a name not declared for the
                workspace, a supplied value's type does not match its
                parameter's declared type, or a required parameter
                has no supplied value and no default
        """

        parameters = self._validated_parameters(workspace_id)

        if values is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError(
                "Cannot validate None parameter values."
            )

        supplied = values.values
        known_names = {parameter.name for parameter in parameters}

        for name in supplied:
            if name not in known_names:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError(
                    f"Cannot validate parameter values: {name!r} is not a supported "
                    f"parameter of workspace ID {workspace_id!r}."
                )

        merged = {}

        for parameter in parameters:
            if parameter.name in supplied:
                value = supplied[parameter.name]

                if parameter.type is not None and not isinstance(value, parameter.type):
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError(
                        f"Cannot validate parameter {parameter.name!r}: expected a value "
                        f"of type {parameter.type.__name__!r}."
                    )

                merged[parameter.name] = value
            elif parameter.default_value is not None:
                merged[parameter.name] = parameter.default_value
            elif parameter.required:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError(
                    f"Cannot validate parameter values: required parameter "
                    f"{parameter.name!r} has no supplied value and no default."
                )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterValues(
            values=MappingProxyType(merged),
        )

    def defaults(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterValues:
        """
        Read the default values declared by a workspace's parameters.

        Args:
            workspace_id: The identifier of the workspace to read
                defaults from

        Returns:
            An immutable set of every parameter's default value, in
            declared parameter order, omitting parameters with no
            default

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError:
                If the workspace ID is None or blank, or its declared
                parameters contain duplicate names
        """

        parameters = self._validated_parameters(workspace_id)

        merged = {
            parameter.name: parameter.default_value
            for parameter in parameters
            if parameter.default_value is not None
        }

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterValues(
            values=MappingProxyType(merged),
        )

    def apply(self, workspace_id: str, values):
        """
        Validate a set of parameter values against a workspace, then
        produce the workspace's configured snapshot.

        Args:
            workspace_id: The identifier of the workspace to
                configure
            values: The parameter values to validate before the
                snapshot is produced

        Returns:
            The configured workspace snapshot produced by the
            underlying workspace service

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError:
                If the parameter values are invalid, as described by
                validate()
        """

        self.validate(workspace_id, values)

        return self._workspace_service.snapshot(workspace_id)

    def supported_parameters(self, workspace_id: str) -> tuple:
        """
        List the parameters a workspace declares, in declared order.

        Returns:
            An immutable tuple of the workspace's declared
            parameters, or an empty tuple if the workspace declares
            none

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError:
                If the workspace ID is None or blank, or its declared
                parameters contain duplicate names
        """

        return self._validated_parameters(workspace_id)

    def _validated_parameters(self, workspace_id: str) -> tuple:
        self._validate_workspace_id(workspace_id)

        parameters = tuple(self._parameter_definitions.get(workspace_id, ()))

        seen_names = set()

        for parameter in parameters:
            if parameter.name in seen_names:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError(
                    f"Cannot operate on workspace ID {workspace_id!r}: duplicate parameter "
                    f"name {parameter.name!r} declared."
                )

            seen_names.add(parameter.name)

        return parameters

    def _validate_workspace_id(self, workspace_id: str) -> None:
        if workspace_id is None or not workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError(
                "Cannot operate on a binding workspace with an empty or blank workspace ID."
            )
