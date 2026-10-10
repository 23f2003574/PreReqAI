from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_release import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRelease,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_release_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseService:
    """
    Promotes consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace versions
    through a controlled release lifecycle (DRAFT -> RELEASED ->
    RETIRED), so that only approved workspace version snapshots can
    be promoted into deployment. Only a (workspace, version) pair
    currently holding RELEASED status is deployable.

    The service's responsibility is release status tracking, not
    workspace creation, membership management, version publication,
    or deployment itself. It does NOT create workspaces, mutate
    workspace membership, publish workspace versions, deploy
    workspaces, mutate the workspace registry or version history,
    persist state externally, log, or publish events. Every
    transition produces a new, immutable release record; no release
    record is ever mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Deterministic: Same sequence of operations always produces the
      same observable state, including the release identifier itself
    - Forward-only: A (workspace, version) pair may only move DRAFT
      -> RELEASED -> RETIRED, never backward or sideways
    - One active release per (workspace_id, version): Re-releasing
      an already released or already retired version is rejected
    - Append-only: Every transition appends a new record to the
      release history; no earlier record is ever mutated or removed
    """

    def __init__(self, workspace_registry, workspace_version_service):
        """
        Args:
            workspace_registry: The registry used to verify a
                workspace exists. Any object exposing
                `find(workspace_id)` is accepted
            workspace_version_service: The version service used to
                verify a version was published for the workspace. Any
                object exposing `find(workspace_id, version)` is
                accepted
        """

        if workspace_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                "Cannot initialize release service with a None workspace registry."
            )

        if workspace_version_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                "Cannot initialize release service with a None workspace version service."
            )

        self._workspace_registry = workspace_registry
        self._workspace_version_service = workspace_version_service
        self._releases = {}
        self._lock = RLock()

    def release(
        self,
        workspace_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseResult:
        """
        Release a workspace version, promoting it from DRAFT to
        RELEASED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError:
                If the workspace ID or version is None or blank, no
                workspace is registered under the workspace ID, no
                version was published for the workspace, or the
                version has already been released or retired
        """

        key = self._key(workspace_id, version)

        with self._lock:
            existing = self._releases.get(key)

            if existing is not None:
                if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RELEASED:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                        f"Cannot release version {version!r} of workspace ID {workspace_id!r}: it has already been released."
                    )

                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                    f"Cannot release version {version!r} of workspace ID {workspace_id!r}: it is retired and cannot be released again."
                )

            previous_status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.DRAFT

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRelease(
                release_id=self._generate_release_id(workspace_id, version),
                workspace_id=workspace_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RELEASED,
                released_at=datetime.now(timezone.utc),
            )

            self._releases[key] = new_release

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseResult(
                previous_status=previous_status,
                current_status=new_release.status,
                release=new_release,
            )

    def retire(
        self,
        workspace_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseResult:
        """
        Retire a released workspace version, demoting it from
        RELEASED to RETIRED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError:
                If the workspace ID or version is None or blank, no
                workspace is registered under the workspace ID, no
                version was published for the workspace, the version
                has never been released, or it has already been
                retired
        """

        key = self._key(workspace_id, version)

        with self._lock:
            existing = self._releases.get(key)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                    f"Cannot retire version {version!r} of workspace ID {workspace_id!r}: it has never been released."
                )

            if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RETIRED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                    f"Cannot retire version {version!r} of workspace ID {workspace_id!r}: it has already been retired."
                )

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRelease(
                release_id=existing.release_id,
                workspace_id=workspace_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RETIRED,
                released_at=existing.released_at,
            )

            self._releases[key] = new_release

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseResult(
                previous_status=existing.status,
                current_status=new_release.status,
                release=new_release,
            )

    def latest_release(self, workspace_id: str):
        """
        Find the most recently released, currently active release
        for a workspace.

        Returns:
            The release record with status RELEASED and the latest
            released_at for the workspace, or None if the workspace
            has no currently released version

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError:
                If the workspace ID is None or blank, or no workspace
                is registered under it
        """

        self._resolve_workspace(workspace_id)

        with self._lock:
            candidates = [
                release
                for release in self._releases.values()
                if (
                    release.workspace_id == workspace_id
                    and release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RELEASED
                )
            ]

        if not candidates:
            return None

        return max(candidates, key=lambda release: release.released_at)

    def is_released(self, workspace_id: str, version: str) -> bool:
        """
        Check whether a (workspace, version) pair currently holds
        RELEASED status. Only a version for which this returns True
        is deployable.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError:
                If the workspace ID or version is None or blank, no
                workspace is registered under the workspace ID, or no
                version was published for the workspace
        """

        key = self._key(workspace_id, version)

        with self._lock:
            existing = self._releases.get(key)

        return (
            existing is not None
            and existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus.RELEASED
        )

    def _key(self, workspace_id: str, version: str):
        self._resolve_workspace(workspace_id)

        self._validate_identifier(version, "version")

        if self._workspace_version_service.find(workspace_id, version) is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                f"Cannot operate: version {version!r} was not found for workspace ID {workspace_id!r}."
            )

        return (workspace_id, version)

    def _resolve_workspace(self, workspace_id: str):
        self._validate_identifier(workspace_id, "workspace ID")

        workspace = self._workspace_registry.find(workspace_id)

        if workspace is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                f"Cannot operate: no workspace is registered under workspace ID {workspace_id!r}."
            )

        return workspace

    def _generate_release_id(self, workspace_id: str, version: str) -> str:
        return f"release::{workspace_id}::{version}"

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                f"Cannot operate with an empty or blank {label}."
            )
