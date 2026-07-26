from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_release import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRelease,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_release_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseService:
    """
    Promotes consumer projection execution capability registry event
    subscription lifecycle policy profile versions through a
    controlled release lifecycle (DRAFT -> RELEASED -> RETIRED)
    before they may be deployed. Only a version currently holding
    RELEASED status is eligible for deployment.

    The service's responsibility is release status tracking, not
    deployment, profile registration, or version publication. It
    does NOT deploy profiles, register profiles, publish versions,
    mutate an existing release record, persist state externally, log,
    or publish events. Every transition produces a new, immutable
    release record; no release record is ever mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Deterministic: Same sequence of operations always produces the
      same observable state
    - Forward-only: A version may only move DRAFT -> RELEASED ->
      RETIRED, never backward or sideways
    - One active release per version: A version cannot be released
      twice without an intervening retirement having never occurred;
      re-releasing an already-released or already-retired version is
      rejected
    """

    def __init__(

        self,

        resolver,

        version_service,

    ):
        """
        Args:
            resolver: The profile resolver used to verify a profile
                exists before it is released or retired. Any object
                exposing `resolve_or_raise(profile_id)` is accepted
            version_service: The version service used to verify a
                version was published before it is released or
                retired. Any object exposing `find(profile_id,
                version)` is accepted
        """

        self._resolver = resolver

        self._version_service = version_service

        self._releases = {}

        self._lock = RLock()

    def release(

        self,

        profile_id,

        version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseResult:
        """
        Release a profile version, promoting it from DRAFT to
        RELEASED.

        Args:
            profile_id: The identifier of the profile the version
                belongs to
            version: The version to release

        Returns:
            An immutable release result carrying the new release
            record

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError:
                If the profile ID or version is None or blank, no
                profile is found under the profile ID, no version is
                published under the version, or the version has
                already been released or retired
        """

        key = self._key(

            profile_id,

            version,
        )

        with self._lock:

            existing = self._releases.get(
                key
            )

            if existing is not None:

                if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RELEASED:

                    raise (
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError(
                            f"Cannot release version {version!r} of profile "
                            f"{profile_id!r}: it has already been released."
                        )
                    )

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError(
                        f"Cannot release version {version!r} of profile "
                        f"{profile_id!r}: it is retired and cannot be "
                        "released again."
                    )
                )

            previous_status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.DRAFT

            new_release = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRelease(
                    profile_id=profile_id,

                    version=version,

                    status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RELEASED,

                    released_at=datetime.now(
                        timezone.utc
                    ),
                )
            )

            self._releases[key] = new_release

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseResult(
                    previous_status=previous_status,

                    current_status=new_release.status,

                    release=new_release,
                )
            )

    def retire(

        self,

        profile_id,

        version,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseResult:
        """
        Retire a released profile version, demoting it from RELEASED
        to RETIRED.

        Args:
            profile_id: The identifier of the profile the version
                belongs to
            version: The version to retire

        Returns:
            An immutable release result carrying the new release
            record

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError:
                If the profile ID or version is None or blank, no
                profile is found under the profile ID, no version is
                published under the version, the version has never
                been released, or the version has already been
                retired
        """

        key = self._key(

            profile_id,

            version,
        )

        with self._lock:

            existing = self._releases.get(
                key
            )

            if existing is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError(
                        f"Cannot retire version {version!r} of profile "
                        f"{profile_id!r}: it has never been released."
                    )
                )

            if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RETIRED:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError(
                        f"Cannot retire version {version!r} of profile "
                        f"{profile_id!r}: it has already been retired."
                    )
                )

            new_release = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRelease(
                    profile_id=profile_id,

                    version=version,

                    status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RETIRED,

                    released_at=existing.released_at,
                )
            )

            self._releases[key] = new_release

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseResult(
                    previous_status=existing.status,

                    current_status=new_release.status,

                    release=new_release,
                )
            )

    def latest_release(

        self,

        profile_id,

    ):
        """
        Find the most recently released, currently active release
        for a profile.

        Args:
            profile_id: The profile ID to look up

        Returns:
            The release record with status RELEASED and the latest
            released_at for the profile, or None if the profile has
            no currently released version

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError:
                If the profile ID is None or blank
        """

        self._validate_identifier(

            profile_id,

            "profile ID",
        )

        with self._lock:

            candidates = [

                release

                for release

                in self._releases.values()

                if (

                    release.profile_id == profile_id

                    and release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RELEASED
                )
            ]

        if not candidates:

            return None

        return max(

            candidates,

            key=lambda release: release.released_at,
        )

    def is_released(

        self,

        profile_id,

        version,

    ) -> bool:
        """
        Check whether a profile version currently holds RELEASED
        status. Only a version for which this returns True is
        eligible for deployment.

        Args:
            profile_id: The identifier of the profile the version
                belongs to
            version: The version to check

        Returns:
            True if the version's current status is RELEASED, False
            otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError:
                If the profile ID or version is None or blank
        """

        key = self._key(

            profile_id,

            version,
        )

        with self._lock:

            existing = self._releases.get(
                key
            )

        return (

            existing is not None

            and existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RELEASED
        )

    def _key(

        self,

        profile_id,

        version,

    ):

        self._validate_identifier(

            profile_id,

            "profile ID",
        )

        self._validate_identifier(

            version,

            "version",
        )

        try:

            self._resolver.resolve_or_raise(
                profile_id
            )

        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolverError as error:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError(
                    "Cannot operate: no profile was found under profile ID "
                    f"{profile_id!r}."
                )
            ) from error

        if self._version_service.find(

            profile_id,

            version,

        ) is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError(
                    f"Cannot operate: version {version!r} was not found "
                    f"for profile ID {profile_id!r}."
                )
            )

        return (

            profile_id,

            version,
        )

    def _validate_identifier(

        self,

        identifier,

        label,

    ) -> None:

        if (

            identifier is None

            or not identifier.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError(
                    f"Cannot operate with an empty or blank {label}."
                )
            )
