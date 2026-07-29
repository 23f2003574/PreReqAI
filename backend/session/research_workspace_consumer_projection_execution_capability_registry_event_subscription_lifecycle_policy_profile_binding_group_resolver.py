from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_resolution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolver:
    """
    Resolves the effective consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    group, and its eligible member bindings, for a group identifier,
    providing a single lookup interface for downstream deployment and
    execution components.

    The resolver's responsibility is centralized, deterministic
    resolution of the effective group and its members for a given
    group ID, not group creation, replacement, removal, validation, or
    persistence. It does NOT create groups, mutate a registry,
    validate groups, persist results, log, or publish events. A
    resolver works against any object exposing a `find(group_id)`
    lookup, such as a binding group registry service, together with a
    binding registry exposing `find(binding_id)` and an activation
    service exposing `state(binding_id)`. Only a binding that is both
    registered and ACTIVE is included among a group's resolved
    members; missing and inactive members are silently skipped, and
    members are returned in the order they are stored on the group.

    The resolver is:
    - Stateless: No mutable instance state; the registries and default
      group it was constructed with are treated as read-only
    - Deterministic: Same group ID and registry state always produce
      the same outcome
    - Side-effect free: Never mutates the group registry, the binding
      registry, or the activation service it resolves against
    """

    def __init__(
        self,
        group_registry,
        binding_registry,
        activation_service,
        default_group=None,
    ):
        """
        Args:
            group_registry: The primary lookup source to resolve
                against. Any object exposing a `find(group_id)`
                lookup is accepted
            binding_registry: The registry used to look up a group's
                member bindings. Any object exposing a
                `find(binding_id)` lookup is accepted
            activation_service: The service used to check whether a
                member binding is eligible to participate in
                resolution. Any object exposing `state(binding_id)` is
                accepted
            default_group: An optional group to fall back to when the
                registry has no group for the group ID

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError:
                If the group registry, binding registry, or activation
                service is None
        """

        if group_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError(
                "Cannot resolve binding groups against a None group registry."
            )

        if binding_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError(
                "Cannot resolve binding groups against a None binding registry."
            )

        if activation_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError(
                "Cannot resolve binding groups against a None activation service."
            )

        self._group_registry = group_registry
        self._binding_registry = binding_registry
        self._activation_service = activation_service
        self._default_group = default_group

    def resolve(
        self,
        group_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult:
        """
        Resolve the effective binding group, and its eligible member
        bindings, for a group ID.

        The group registry is consulted first. If it has no group for
        the group ID and a default group was configured, the default
        group is used instead.

        Returns:
            An immutable resolution result. If no group is found in
            any configured source, resolved is False, group is None,
            bindings is empty, and source is None

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError:
                If the group ID is None or blank, or the resolved
                group's membership is corrupted
        """

        self._validate_group_id(group_id)

        group = self._group_registry.find(group_id)
        source = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource.REGISTRY

        if group is None:
            group = self._default_group
            source = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionSource.DEFAULT

        if group is None:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult(
                group=None,
                bindings=(),
                resolved=False,
                source=None,
            )

        self._validate_group_membership(group)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolutionResult(
            group=group,
            bindings=self._resolve_members(group),
            resolved=True,
            source=source,
        )

    def resolve_or_raise(
        self,
        group_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup:
        """
        Resolve the effective binding group for a group ID, raising if
        it cannot be resolved.

        Returns:
            The resolved group

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError:
                If the group ID is None or blank, or no group could be
                resolved for it
        """

        result = self.resolve(group_id)

        if not result.resolved:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError(
                f"Cannot resolve a binding group for group ID {group_id!r}: no group was found."
            )

        return result.group

    def contains(self, group_id: str) -> bool:
        """
        Check whether an effective binding group can be resolved for a
        group ID.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError:
                If the group ID is None or blank
        """

        return self.resolve(group_id).resolved

    def resolve_bindings(self, group_id: str) -> tuple:
        """
        Resolve a group's eligible member bindings, in stored order.

        Returns:
            An immutable tuple of the group's registered, ACTIVE
            member bindings, or an empty tuple if the group cannot be
            resolved

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError:
                If the group ID is None or blank
        """

        return self.resolve(group_id).bindings

    def _resolve_members(self, group) -> tuple:
        resolved = []

        for binding_id in group.binding_ids:
            binding = self._binding_registry.find(binding_id)

            if binding is None:
                continue

            if (
                self._activation_service.state(binding_id)
                != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE
            ):
                continue

            resolved.append(binding)

        return tuple(resolved)

    def _validate_group_id(self, group_id: str) -> None:
        if group_id is None or not group_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError(
                "Cannot resolve a binding group with an empty or blank group ID."
            )

    def _validate_group_membership(self, group) -> None:
        if not isinstance(
            group,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError(
                "Cannot resolve a binding group: group membership is corrupted."
            )

        try:
            binding_ids = tuple(group.binding_ids)
        except TypeError as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError(
                "Cannot resolve a binding group: group membership is corrupted."
            ) from error

        if any(binding_id is None or not isinstance(binding_id, str) or not binding_id.strip() for binding_id in binding_ids):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupResolverError(
                "Cannot resolve a binding group: group membership is corrupted."
            )
