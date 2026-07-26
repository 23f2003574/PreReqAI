from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_collection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCollection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService:
    """
    Maintains a dedicated collection of consumer projection
    execution capability registry event subscription lifecycle
    policy profiles, grouping reusable lifecycle policies under
    named configurations for different deployment environments.

    The service's responsibility is profile registration,
    replacement, removal, and lookup, not policy evaluation,
    lifecycle transition execution, persistence, logging, or event
    publication. It does NOT validate the policies a profile refers
    to, evaluate policies, execute lifecycle transitions, persist
    the collection, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an
      internal lock
    - Duplicate-free: No two registered profiles may share a
      profile ID
    - Order-preserving: Profiles are listed in the order they were
      first registered
    """

    def __init__(self):

        self._collection = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCollection(
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
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError:
                If the profile is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
                has an empty or blank profile ID, or its profile ID
                is already registered
        """

        self._validate_profile(
            profile
        )

        with self._lock:

            if profile.profile_id in self._collection.profiles:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError(
                        "Cannot register a profile: profile ID "
                        f"{profile.profile_id!r} is already registered."
                    )
                )

            updated = dict(
                self._collection.profiles
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
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError:
                If the profile is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
                has an empty or blank profile ID, or no profile is
                registered under its profile ID
        """

        self._validate_profile(
            profile
        )

        with self._lock:

            if profile.profile_id not in self._collection.profiles:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError(
                        "Cannot replace a profile: no profile is "
                        f"registered under profile ID {profile.profile_id!r}."
                    )
                )

            updated = dict(
                self._collection.profiles
            )

            updated[profile.profile_id] = profile

            self._replace_profiles(
                updated
            )

    def remove(

        self,

        profile_id,

    ) -> None:
        """
        Remove the profile registered under a profile ID.

        Removing a profile ID that was never registered is rejected
        rather than treated as a no-op.

        Args:
            profile_id: The profile ID to remove

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError:
                If the profile ID is None or blank, or no profile is
                registered under it
        """

        self._validate_profile_id(
            profile_id
        )

        with self._lock:

            if profile_id not in self._collection.profiles:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError(
                        "Cannot remove a profile: no profile is "
                        f"registered under profile ID {profile_id!r}."
                    )
                )

            updated = dict(
                self._collection.profiles
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

            return self._collection.profiles.get(
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

            return profile_id in self._collection.profiles

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
                self._collection.profiles.values()
            )

    def _replace_profiles(

        self,

        profiles,

    ) -> None:

        self._collection = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCollection(
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
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError(
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
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError(
                    "Cannot register a None profile."
                )
            )

        if not isinstance(

            profile,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError(
                    "Cannot register a profile: profile must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile."
                )
            )

        self._validate_profile_id(
            profile.profile_id
        )
