from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_release import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRelease,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_release_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseService:
    """
    Promotes consumer projection execution capability registry event
    subscription lifecycle policy profile binding group versions
    through a controlled release lifecycle (DRAFT -> RELEASED ->
    RETIRED), so that only approved group version snapshots can be
    promoted into deployment. Only a (group, version) pair currently
    holding RELEASED status is deployable.

    The service's responsibility is release status tracking, not
    group creation, membership management, version publication, or
    deployment itself. It does NOT create groups, mutate group
    membership, publish group versions, deploy groups, mutate the
    group registry or version history, persist state externally,
    log, or publish events. Every transition produces a new,
    immutable release record; no release record is ever mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Deterministic: Same sequence of operations always produces the
      same observable state, including the release identifier itself
    - Forward-only: A (group, version) pair may only move DRAFT ->
      RELEASED -> RETIRED, never backward or sideways
    - One active release per (group_id, version): Re-releasing an
      already released or already retired version is rejected
    - Append-only: Every transition appends a new record to the
      release history; no earlier record is ever mutated or removed
    """

    def __init__(self, group_registry, group_version_service):
        """
        Args:
            group_registry: The registry used to verify a group
                exists. Any object exposing `find(group_id)` is
                accepted
            group_version_service: The version service used to verify
                a version was published for the group. Any object
                exposing `find(group_id, version)` is accepted
        """

        if group_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError(
                "Cannot initialize release service with a None group registry."
            )

        if group_version_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError(
                "Cannot initialize release service with a None group version service."
            )

        self._group_registry = group_registry
        self._group_version_service = group_version_service
        self._releases = {}
        self._lock = RLock()

    def release(
        self,
        group_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseResult:
        """
        Release a group version, promoting it from DRAFT to
        RELEASED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError:
                If the group ID or version is None or blank, no group
                is registered under the group ID, no version was
                published for the group, or the version has already
                been released or retired
        """

        key = self._key(group_id, version)

        with self._lock:
            existing = self._releases.get(key)

            if existing is not None:
                if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RELEASED:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError(
                        f"Cannot release version {version!r} of group ID {group_id!r}: it has already been released."
                    )

                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError(
                    f"Cannot release version {version!r} of group ID {group_id!r}: it is retired and cannot be released again."
                )

            previous_status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.DRAFT

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRelease(
                release_id=self._generate_release_id(group_id, version),
                group_id=group_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RELEASED,
                released_at=datetime.now(timezone.utc),
            )

            self._releases[key] = new_release

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseResult(
                previous_status=previous_status,
                current_status=new_release.status,
                release=new_release,
            )

    def retire(
        self,
        group_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseResult:
        """
        Retire a released group version, demoting it from RELEASED
        to RETIRED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError:
                If the group ID or version is None or blank, no group
                is registered under the group ID, no version was
                published for the group, the version has never been
                released, or it has already been retired
        """

        key = self._key(group_id, version)

        with self._lock:
            existing = self._releases.get(key)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError(
                    f"Cannot retire version {version!r} of group ID {group_id!r}: it has never been released."
                )

            if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RETIRED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError(
                    f"Cannot retire version {version!r} of group ID {group_id!r}: it has already been retired."
                )

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRelease(
                release_id=existing.release_id,
                group_id=group_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RETIRED,
                released_at=existing.released_at,
            )

            self._releases[key] = new_release

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseResult(
                previous_status=existing.status,
                current_status=new_release.status,
                release=new_release,
            )

    def latest_release(self, group_id: str):
        """
        Find the most recently released, currently active release
        for a group.

        Returns:
            The release record with status RELEASED and the latest
            released_at for the group, or None if the group has no
            currently released version

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError:
                If the group ID is None or blank, or no group is
                registered under it
        """

        self._resolve_group(group_id)

        with self._lock:
            candidates = [
                release
                for release in self._releases.values()
                if (
                    release.group_id == group_id
                    and release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RELEASED
                )
            ]

        if not candidates:
            return None

        return max(candidates, key=lambda release: release.released_at)

    def is_released(self, group_id: str, version: str) -> bool:
        """
        Check whether a (group, version) pair currently holds
        RELEASED status. Only a version for which this returns True
        is deployable.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError:
                If the group ID or version is None or blank, no group
                is registered under the group ID, or no version was
                published for the group
        """

        key = self._key(group_id, version)

        with self._lock:
            existing = self._releases.get(key)

        return (
            existing is not None
            and existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RELEASED
        )

    def _key(self, group_id: str, version: str):
        self._resolve_group(group_id)

        self._validate_identifier(version, "version")

        if self._group_version_service.find(group_id, version) is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError(
                f"Cannot operate: version {version!r} was not found for group ID {group_id!r}."
            )

        return (group_id, version)

    def _resolve_group(self, group_id: str):
        self._validate_identifier(group_id, "group ID")

        group = self._group_registry.find(group_id)

        if group is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError(
                f"Cannot operate: no group is registered under group ID {group_id!r}."
            )

        return group

    def _generate_release_id(self, group_id: str, version: str) -> str:
        return f"release::{group_id}::{version}"

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError(
                f"Cannot operate with an empty or blank {label}."
            )
