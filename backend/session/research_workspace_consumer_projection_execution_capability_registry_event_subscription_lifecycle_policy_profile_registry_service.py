from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_registry_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistrySnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService:
    """
    Maintains a dedicated registry of consumer projection execution
    capability registry event subscription lifecycle policy
    profiles, managed independently from any runtime lifecycle
    policy.

    The service's responsibility is profile registration,
    replacement, unregistration, lookup, and snapshot generation,
    not profile validation, versioning, policy evaluation, lifecycle
    transition execution, persistence, logging, or event
    publication. It does NOT validate profiles, publish versions,
    evaluate policies, execute lifecycle transitions, persist the
    registry, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an
      internal lock
    - Duplicate-free: No two registered profiles may share a
      profile ID
    - Order-preserving: Profiles are listed in the order they were
      first registered
    """

    def __init__(self):

        self._registry = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistry(
                profiles=MappingProxyType({})
            )
        )

        self._lock = RLock()

    def register(

        self,

        profile,

    ) -> None:
        """
        Register a lifecycle policy profile.

        Args:
            profile: The profile to register

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError:
                If the profile is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
                has an empty or blank profile ID, or its profile ID
                is already registered
        """

        self._validate_profile(
            profile
        )

        with self._lock:

            if profile.profile_id in self._registry.profiles:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError(
                        "Cannot register a profile: profile ID "
                        f"{profile.profile_id!r} is already registered."
                    )
                )

            updated = dict(
                self._registry.profiles
            )

            updated[profile.profile_id] = profile

            self._replace_profiles(
                updated
            )

    def replace(

        self,

        profile,

    ) -> None:
        """
        Replace an already-registered lifecycle policy profile.

        The replaced profile keeps its original position in
        registration order.

        Args:
            profile: The profile to replace the existing one with

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError:
                If the profile is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
                has an empty or blank profile ID, or no profile is
                registered under its profile ID
        """

        self._validate_profile(
            profile
        )

        with self._lock:

            if profile.profile_id not in self._registry.profiles:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError(
                        "Cannot replace a profile: no profile is "
                        f"registered under profile ID {profile.profile_id!r}."
                    )
                )

            updated = dict(
                self._registry.profiles
            )

            updated[profile.profile_id] = profile

            self._replace_profiles(
                updated
            )

    def unregister(

        self,

        profile_id,

    ) -> None:
        """
        Unregister the profile registered under a profile ID.

        Unlike a plain removal, unregistering a profile ID that was
        never registered is rejected rather than treated as a
        no-op.

        Args:
            profile_id: The profile ID to unregister

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError:
                If the profile ID is None or blank, or no profile is
                registered under it
        """

        self._validate_profile_id(
            profile_id
        )

        with self._lock:

            if profile_id not in self._registry.profiles:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError(
                        "Cannot unregister a profile: no profile is "
                        f"registered under profile ID {profile_id!r}."
                    )
                )

            updated = dict(
                self._registry.profiles
            )

            del updated[profile_id]

            self._replace_profiles(
                updated
            )

    def find(

        self,

        profile_id,

    ):
        """
        Find the profile registered under a profile ID.

        Args:
            profile_id: The profile ID to look up

        Returns:
            The matching profile, or None if no profile is
            registered under it
        """

        with self._lock:

            return self._registry.profiles.get(
                profile_id
            )

    def contains(

        self,

        profile_id,

    ) -> bool:
        """
        Check whether a profile is registered under a profile ID.

        Args:
            profile_id: The profile ID to check

        Returns:
            True if a profile is registered under the profile ID,
            False otherwise
        """

        with self._lock:

            return profile_id in self._registry.profiles

    def list(

        self,

    ) -> tuple:
        """
        List every registered profile.

        Returns:
            An immutable tuple of every registered profile,
            preserving registration order
        """

        with self._lock:

            return tuple(
                self._registry.profiles.values()
            )

    def snapshot(

        self,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistrySnapshot:
        """
        Take a snapshot of the registry's current state.

        Returns:
            An immutable snapshot carrying the current profile
            count and every registered profile's identifier,
            preserving registration order
        """

        with self._lock:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistrySnapshot(
                    profile_count=len(
                        self._registry.profiles
                    ),

                    profile_identifiers=tuple(
                        self._registry.profiles.keys()
                    ),
                )
            )

    def _replace_profiles(

        self,

        profiles,

    ) -> None:

        self._registry = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistry(
                profiles=MappingProxyType(
                    profiles
                )
            )
        )

    def _validate_profile_id(

        self,

        profile_id,

    ) -> None:

        if (

            profile_id is None

            or not profile_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError(
                    "Cannot operate on a profile with an empty or blank "
                    "profile ID."
                )
            )

    def _validate_profile(

        self,

        profile,

    ) -> None:

        if profile is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError(
                    "Cannot register a None profile."
                )
            )

        if not isinstance(

            profile,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError(
                    "Cannot register a profile: profile must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile."
                )
            )

        self._validate_profile_id(
            profile.profile_id
        )
