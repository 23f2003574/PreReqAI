from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_resolution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolver:
    """
    Resolves the effective profile assignment for a target identifier
    against an assignment registry, with optional fallback to a
    default assignment.

    The resolver's responsibility is centralized, deterministic
    resolution of the active profile assignment for a given target,
    not assignment creation, replacement, removal, validation, or
    persistence. It does NOT register assignments, mutate a registry,
    validate assignments, persist results, log, or publish events.
    A resolver works against any object exposing a
    `find(target_id)` lookup, such as an assignment registry service
    or assignment service.

    The resolver is:
    - Stateless: No mutable instance state; the registry and default
      assignment it was constructed with are treated as read-only
    - Deterministic: Same target ID and registry state always produce
      the same outcome
    - Side-effect free: Never mutates the registry it resolves
      against
    """

    def __init__(

        self,

        registry,

        default_assignment=None,

    ):
        """
        Args:
            registry: The primary lookup source to resolve against.
                Any object exposing a `find(target_id)` lookup is
                accepted
            default_assignment: An optional assignment to fall back
                to when the registry has no active assignment for the
                target

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError:
                If the registry is None
        """

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError(
                    "Cannot resolve assignments against a None registry."
                )
            )

        self._registry = registry

        self._default_assignment = default_assignment

    def resolve(

        self,

        target_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult:
        """
        Resolve the active profile assignment for a target.

        The registry is consulted first. If it has no active
        assignment for the target and a default assignment was
        configured, the default assignment is returned.

        Args:
            target_id: The target ID to resolve an assignment for

        Returns:
            An immutable resolution result. If no assignment is
            found in any configured source, resolved is False,
            assignment is None, and resolution_source is None

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError:
                If the target ID is None or blank
        """

        self._validate_target_id(
            target_id
        )

        registry_match = self._registry.find(
            target_id
        )

        if registry_match is not None:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult(
                    target_id=target_id,

                    assignment=registry_match,

                    resolved=True,

                    resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource.REGISTRY,
                )
            )

        if self._default_assignment is not None:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult(
                    target_id=target_id,

                    assignment=self._default_assignment,

                    resolved=True,

                    resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource.DEFAULT,
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult(
                target_id=target_id,

                assignment=None,

                resolved=False,

                resolution_source=None,
            )
        )

    def resolve_or_raise(

        self,

        target_id,

    ):
        """
        Resolve the active profile assignment for a target, raising
        if it cannot be resolved.

        Args:
            target_id: The target ID to resolve an assignment for

        Returns:
            The resolved assignment

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError:
                If the target ID is None or blank, or no assignment
                could be resolved for it
        """

        result = self.resolve(
            target_id
        )

        if not result.resolved:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError(
                    f"Cannot resolve assignment for target ID {target_id!r}: "
                    "no active assignment was found."
                )
            )

        return result.assignment

    def can_resolve(

        self,

        target_id,

    ) -> bool:
        """
        Check whether an active assignment can be resolved for a
        target ID.

        Args:
            target_id: The target ID to check

        Returns:
            True if an active assignment can be resolved for the
            target ID, False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError:
                If the target ID is None or blank
        """

        return self.resolve(
            target_id
        ).resolved

    def _validate_target_id(

        self,

        target_id,

    ) -> None:

        if (

            target_id is None

            or not target_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolverError(
                    "Cannot resolve an assignment with an empty or blank "
                    "target ID."
                )
            )
