from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_resolution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolver:
    """
    Resolves the effective consumer projection execution capability
    registry event subscription lifecycle policy profile binding for
    an execution capability identifier, providing a single lookup
    interface for execution components.

    The resolver's responsibility is centralized, deterministic
    resolution of the effective binding for a given capability, not
    binding creation, replacement, removal, validation, or
    persistence. It does NOT create bindings, mutate a registry,
    validate bindings, persist results, log, or publish events. A
    resolver works against any object exposing a
    `find_by_capability(capability_id)` lookup that returns a
    collection carrying a `bindings` tuple, such as a profile binding
    service. When more than one binding is registered for a
    capability, the earliest-bound one is the effective binding.

    The resolver is:
    - Stateless: No mutable instance state; the registry and default
      binding it was constructed with are treated as read-only
    - Deterministic: Same capability ID and registry state always
      produce the same outcome
    - Side-effect free: Never mutates the registry it resolves
      against
    """

    def __init__(
        self,
        registry,
        default_binding=None,
    ):
        """
        Args:
            registry: The primary lookup source to resolve against.
                Any object exposing a
                `find_by_capability(capability_id)` lookup is
                accepted
            default_binding: An optional binding to fall back to when
                the registry has no binding for the capability

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError:
                If the registry is None
        """

        if registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError(
                "Cannot resolve bindings against a None registry."
            )

        self._registry = registry
        self._default_binding = default_binding

    def resolve(
        self,
        capability_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult:
        """
        Resolve the effective profile binding for a capability.

        The registry is consulted first. If it has no binding for the
        capability and a default binding was configured, the default
        binding is returned.

        Returns:
            An immutable resolution result. If no binding is found in
            any configured source, resolved is False, binding is
            None, and source is None

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError:
                If the capability ID is None or blank
        """

        self._validate_capability_id(capability_id)

        registry_matches = self._registry.find_by_capability(capability_id).bindings

        if registry_matches:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult(
                capability_id=capability_id,
                binding=registry_matches[0],
                resolved=True,
                source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource.REGISTRY,
            )

        if self._default_binding is not None:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult(
                capability_id=capability_id,
                binding=self._default_binding,
                resolved=True,
                source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionSource.DEFAULT,
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolutionResult(
            capability_id=capability_id,
            binding=None,
            resolved=False,
            source=None,
        )

    def resolve_or_raise(self, capability_id: str):
        """
        Resolve the effective profile binding for a capability,
        raising if it cannot be resolved.

        Returns:
            The resolved binding

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError:
                If the capability ID is None or blank, or no binding
                could be resolved for it
        """

        result = self.resolve(capability_id)

        if not result.resolved:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError(
                f"Cannot resolve a binding for capability ID {capability_id!r}: no binding was found."
            )

        return result.binding

    def can_resolve(self, capability_id: str) -> bool:
        """
        Check whether an effective binding can be resolved for a
        capability ID.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError:
                If the capability ID is None or blank
        """

        return self.resolve(capability_id).resolved

    def _validate_capability_id(self, capability_id: str) -> None:
        if capability_id is None or not capability_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingResolverError(
                "Cannot resolve a binding with an empty or blank capability ID."
            )
