from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_version_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionHistory,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService:
    """
    Maintains the version history of consumer projection execution
    capability registry event subscription lifecycle policy
    profiles, and manages rollback between previously published
    versions.

    The service's responsibility is version publication, lookup,
    history tracking, and rollback, not profile registration, policy
    evaluation, lifecycle transition execution, persistence, logging,
    or event publication. It does NOT register profiles, evaluate
    policies, execute lifecycle transitions, persist history, log,
    or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an
      internal lock
    - Duplicate-free: No two versions published for the same
      profile may share a version identifier
    - Order-preserving: Versions are listed in the order they were
      published
    - Non-destructive: Rollback changes which version is current
      without removing any version from history
    """

    def __init__(self):

        self._histories = {}

        self._lock = RLock()

    def publish(

        self,

        profile_id,

        version,

    ) -> None:
        """
        Publish a new version for a profile.

        Args:
            profile_id: The identifier of the profile to publish a
                version for
            version: The
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion
                to publish

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError:
                If the profile ID is None or blank, the version is
                None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
                has an empty or blank version identifier, has a
                missing policy identifier collection, or a version
                with the same identifier has already been published
                for this profile
        """

        self._validate_profile_id(
            profile_id
        )

        self._validate_version(
            version
        )

        with self._lock:

            existing = self._histories.get(
                profile_id
            )

            if existing is not None and any(

                published.version == version.version

                for published

                in existing.versions
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError(
                        "Cannot publish a version: version "
                        f"{version.version!r} has already been published "
                        f"for profile ID {profile_id!r}."
                    )
                )

            previous_versions = (
                existing.versions
                if existing is not None
                else ()
            )

            self._histories[profile_id] = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionHistory(
                    profile_id=profile_id,

                    current_version=version.version,

                    versions=previous_versions + (version,),
                )
            )

    def latest(

        self,

        profile_id,

    ):
        """
        Find the current version for a profile.

        Args:
            profile_id: The profile ID to look up

        Returns:
            The current
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
            or None if no version has been published for the profile
        """

        with self._lock:

            history = self._histories.get(
                profile_id
            )

        if history is None:

            return None

        return self._find_version(

            history,

            history.current_version,
        )

    def find(

        self,

        profile_id,

        version,

    ):
        """
        Find a specific published version for a profile.

        Args:
            profile_id: The profile ID to look up
            version: The version identifier to look up

        Returns:
            The matching
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
            or None if no such version has been published for the
            profile
        """

        with self._lock:

            history = self._histories.get(
                profile_id
            )

        if history is None:

            return None

        return self._find_version(

            history,

            version,
        )

    def history(

        self,

        profile_id,

    ):
        """
        Read the full version history for a profile.

        Args:
            profile_id: The profile ID to look up

        Returns:
            The profile's immutable
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionHistory,
            or None if no version has been published for the profile
        """

        with self._lock:

            return self._histories.get(
                profile_id
            )

    def rollback(

        self,

        profile_id,

        version,

    ) -> None:
        """
        Roll a profile back to a previously published version.

        Rollback only changes which version is current; it never
        removes a version from history, including versions published
        after the version being rolled back to.

        Args:
            profile_id: The identifier of the profile to roll back
            version: The version identifier to roll back to

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError:
                If the profile ID or version is None or blank, no
                version has ever been published for the profile, or
                the version was never published for the profile
        """

        self._validate_profile_id(
            profile_id
        )

        self._validate_version_identifier(
            version
        )

        with self._lock:

            existing = self._histories.get(
                profile_id
            )

            if existing is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError(
                        "Cannot roll back profile ID "
                        f"{profile_id!r}: no version has ever been "
                        "published for it."
                    )
                )

            if self._find_version(existing, version) is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError(
                        f"Cannot roll back to version {version!r}: it was "
                        f"never published for profile ID {profile_id!r}."
                    )
                )

            self._histories[profile_id] = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionHistory(
                    profile_id=existing.profile_id,

                    current_version=version,

                    versions=existing.versions,
                )
            )

    def _find_version(

        self,

        history,

        version,

    ):

        for published in history.versions:

            if published.version == version:

                return published

        return None

    def _validate_profile_id(

        self,

        profile_id,

    ) -> None:

        if (

            profile_id is None

            or not profile_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError(
                    "Cannot operate on a profile with an empty or blank "
                    "profile ID."
                )
            )

    def _validate_version_identifier(

        self,

        version,

    ) -> None:

        if (

            version is None

            or not version.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError(
                    "Cannot operate with an empty or blank version "
                    "identifier."
                )
            )

    def _validate_version(

        self,

        version,

    ) -> None:

        if version is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError(
                    "Cannot publish a None version."
                )
            )

        if not isinstance(

            version,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError(
                    "Cannot publish a version: version must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion."
                )
            )

        self._validate_version_identifier(
            version.version
        )

        if version.policy_identifiers is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError(
                    "Cannot publish a version with a missing policy "
                    "identifier collection."
                )
            )
