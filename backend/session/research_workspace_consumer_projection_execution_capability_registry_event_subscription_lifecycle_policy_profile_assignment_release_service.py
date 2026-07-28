from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_release import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRelease,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_release_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseService:
    """
    Promotes consumer projection execution capability registry event
    subscription lifecycle policy profile assignment versions through
    a controlled release lifecycle (DRAFT -> RELEASED -> RETIRED) so
    that only approved assignment configuration sets can be promoted
    and activated. Only a version currently holding RELEASED status
    is deployable.

    The service's responsibility is release status tracking, not
    assignment, profile registration, or configuration publication.
    It does NOT assign profiles, register profiles, mutate an
    existing release record, persist state externally, log, or
    publish events. Every transition produces a new, immutable
    release record; no release record is ever mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Deterministic: Same sequence of operations always produces the
      same observable state, including the release identifier itself
    - Forward-only: A version may only move DRAFT -> RELEASED ->
      RETIRED, never backward or sideways
    - One active release per version: Re-releasing an already
      released or already retired version is rejected
    - Append-only: Every transition appends a new record to the
      release history; no earlier record is ever mutated or removed
    """

    def __init__(self):
        self._releases = {}
        self._history = ()
        self._lock = RLock()

    def release(
        self,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseResult:
        """
        Release an assignment configuration version, promoting it
        from DRAFT to RELEASED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError:
                If version is None or blank, or the version has
                already been released or retired
        """

        self._validate_version(version)

        with self._lock:
            existing = self._releases.get(version)

            if existing is not None:
                if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RELEASED:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError(
                        f"Cannot release version {version!r}: it has already been released."
                    )

                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError(
                    f"Cannot release version {version!r}: it is retired and cannot be released again."
                )

            previous_status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.DRAFT

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRelease(
                release_id=self._generate_release_id(version),
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RELEASED,
                released_at=datetime.now(timezone.utc),
            )

            self._releases[version] = new_release
            self._history = self._history + (new_release,)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseResult(
                previous_status=previous_status,
                current_status=new_release.status,
                release=new_release,
            )

    def retire(
        self,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseResult:
        """
        Retire a released assignment configuration version, demoting
        it from RELEASED to RETIRED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError:
                If version is None or blank, the version has never
                been released, or the version has already been
                retired
        """

        self._validate_version(version)

        with self._lock:
            existing = self._releases.get(version)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError(
                    f"Cannot retire version {version!r}: it has never been released."
                )

            if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RETIRED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError(
                    f"Cannot retire version {version!r}: it has already been retired."
                )

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRelease(
                release_id=existing.release_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RETIRED,
                released_at=existing.released_at,
            )

            self._releases[version] = new_release
            self._history = self._history + (new_release,)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseResult(
                previous_status=existing.status,
                current_status=new_release.status,
                release=new_release,
            )

    def latest_release(self):
        """
        Find the most recently released, currently active release
        across every version.

        Returns:
            The release record with status RELEASED and the latest
            released_at, or None if no version is currently released
        """

        with self._lock:
            candidates = [
                release
                for release in self._releases.values()
                if release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RELEASED
            ]

        if not candidates:
            return None

        return max(candidates, key=lambda release: release.released_at)

    def is_released(self, version: str) -> bool:
        """
        Check whether an assignment configuration version currently
        holds RELEASED status. Only a version for which this returns
        True is deployable.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError:
                If version is None or blank
        """

        self._validate_version(version)

        with self._lock:
            existing = self._releases.get(version)

        return (
            existing is not None
            and existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus.RELEASED
        )

    def _generate_release_id(self, version: str) -> str:
        return f"release::{version}"

    def _validate_version(self, version: str) -> None:
        if version is None or not version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError(
                "Cannot operate with an empty or blank version."
            )
