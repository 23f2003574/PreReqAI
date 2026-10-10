from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_resolution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver:
    """
    Resolves a consumer projection execution capability registry
    event subscription lifecycle policy profile by identifier
    against a registry, with optional fallback to a cache and a
    default profile.

    The resolver's responsibility is centralized, deterministic
    resolution, not registration, replacement, unregistration,
    validation, or versioning. It does NOT register profiles,
    mutate a registry or cache, validate profiles, publish
    versions, persist results, log, or publish events. A resolver
    works against any object exposing a `find(profile_id)` lookup,
    such as a profile registry service or profile service.

    The resolver is:
    - Stateless: No mutable instance state; the registry, cache, and
      default profile it was constructed with are treated as
      read-only
    - Deterministic: Same profile ID and lookup source states
      always produce the same outcome
    - Side-effect free: Never mutates the registry or cache it
      resolves against
    """

    def __init__(

        self,

        registry,

        cache=None,

        default_profile=None,

    ):
        """
        Args:
            registry: The primary lookup source to resolve against.
                Any object exposing a `find(profile_id)` lookup is
                accepted
            cache: An optional secondary lookup source consulted
                when the registry has no match. Any object exposing
                a `find(profile_id)` lookup is accepted
            default_profile: An optional profile to fall back to
                when neither the registry nor the cache has a match

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError:
                If the registry is None
        """

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError(
                    "Cannot resolve profiles against a None registry."
                )
            )

        self._registry = registry

        self._cache = cache

        self._default_profile = default_profile

    def resolve(

        self,

        profile_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult:
        """
        Resolve a profile by identifier.

        The registry is consulted first. If it has no match and a
        cache was configured, the cache is consulted next. If
        neither has a match and a default profile was configured,
        the default profile is returned.

        Args:
            profile_id: The profile ID to resolve

        Returns:
            An immutable resolution result. If no match is found in
            any configured source, resolved is False, profile is
            None, and resolution_source is None

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError:
                If the profile ID is None or blank
        """

        self._validate_profile_id(
            profile_id
        )

        registry_match = self._registry.find(
            profile_id
        )

        if registry_match is not None:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult(
                    profile=registry_match,

                    resolved=True,

                    resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource.REGISTRY,
                )
            )

        if self._cache is not None:

            cache_match = self._cache.find(
                profile_id
            )

            if cache_match is not None:

                return (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult(
                        profile=cache_match,

                        resolved=True,

                        resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource.CACHE,
                    )
                )

        if self._default_profile is not None:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult(
                    profile=self._default_profile,

                    resolved=True,

                    resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionSource.DEFAULT,
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolutionResult(
                profile=None,

                resolved=False,

                resolution_source=None,
            )
        )

    def resolve_or_raise(

        self,

        profile_id,

    ):
        """
        Resolve a profile by identifier, raising if it cannot be
        resolved.

        Args:
            profile_id: The profile ID to resolve

        Returns:
            The resolved profile

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError:
                If the profile ID is None or blank, or no profile
                could be resolved for it
        """

        result = self.resolve(
            profile_id
        )

        if not result.resolved:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError(
                    f"Cannot resolve profile ID {profile_id!r}: no "
                    "matching profile was found."
                )
            )

        return result.profile

    def can_resolve(

        self,

        profile_id,

    ) -> bool:
        """
        Check whether a profile ID can be resolved.

        Args:
            profile_id: The profile ID to check

        Returns:
            True if a profile can be resolved for the profile ID,
            False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError:
                If the profile ID is None or blank
        """

        return self.resolve(
            profile_id
        ).resolved

    def _validate_profile_id(

        self,

        profile_id,

    ) -> None:

        if (

            profile_id is None

            or not profile_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError(
                    "Cannot resolve a profile with an empty or blank "
                    "profile ID."
                )
            )
