from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_version_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionHistory,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService:
    """
    Publishes and tracks immutable version snapshots of consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspaces, so editing, review,
    and deployment always operate on a stable revision instead of a
    workspace's mutable, current definition.

    The service's responsibility is version publication, lookup, and
    rollback, not workspace registration, membership management, or
    persistence. It does NOT register workspaces, mutate workspace
    membership, mutate a published version, persist history
    externally, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two versions published for the same
      workspace may share a version identifier
    - Append-only: A published version is never replaced or removed;
      a rollback publishes a new version rather than reverting one
    - Chronological: Versions are listed in the order they were
      published
    """

    def __init__(self, workspace_service):
        """
        Args:
            workspace_service: The service used to capture a
                workspace's immutable snapshot at publish time. Any
                object exposing `find(workspace_id)` and
                `snapshot(workspace_id)` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError:
                If the workspace service is None
        """

        if workspace_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                "Cannot initialize binding workspace version service with a None workspace service."
            )

        self._workspace_service = workspace_service
        self._histories = {}
        self._lock = RLock()

    def publish(
        self,
        workspace_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion:
        """
        Publish a new version snapshot of a workspace's current
        state.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError:
                If the workspace ID or version is None or blank, no
                workspace is registered under the workspace ID, or
                the version has already been published for the
                workspace
        """

        self._validate_identifier(workspace_id, "workspace ID")
        self._validate_identifier(version, "version")

        if self._workspace_service.find(workspace_id) is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                f"Cannot publish: no workspace is registered under workspace ID {workspace_id!r}."
            )

        with self._lock:
            existing_versions = self._existing_versions(workspace_id)

            if any(existing.version == version for existing in existing_versions):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                    f"Cannot publish: version {version!r} has already been published for workspace ID {workspace_id!r}."
                )

            snapshot = self._workspace_service.snapshot(workspace_id)

            published = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion(
                version=version,
                snapshot_id=str(uuid4()),
                created_at=snapshot.created_at,
            )

            self._histories[workspace_id] = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionHistory(
                workspace_id=workspace_id,
                current_version=version,
                versions=existing_versions + (published,),
            )

            return published

    def latest(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion:
        """
        Look up a workspace's currently effective version.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError:
                If the workspace ID is None or blank, or no version
                has ever been published for the workspace
        """

        history = self.history(workspace_id)

        return self._find_version(history, history.current_version)

    def find(self, workspace_id: str, version: str):
        """
        Find a specific published version of a workspace.

        Returns:
            The matching version, or None if no workspace is
            registered under the workspace ID, or the version was
            never published for it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError:
                If the workspace ID or version is None or blank
        """

        self._validate_identifier(workspace_id, "workspace ID")
        self._validate_identifier(version, "version")

        with self._lock:
            history = self._histories.get(workspace_id)

        if history is None:
            return None

        return self._find_version(history, version)

    def history(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionHistory:
        """
        Get the complete version history of a workspace.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError:
                If the workspace ID is None or blank, or no version
                has ever been published for the workspace
        """

        self._validate_identifier(workspace_id, "workspace ID")

        with self._lock:
            history = self._histories.get(workspace_id)

        if history is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                f"Cannot get history: no version has ever been published for workspace ID {workspace_id!r}."
            )

        return history

    def rollback(
        self,
        workspace_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion:
        """
        Roll a workspace back to a previously published version.

        The rollback publishes a new version, pointing at the same
        immutable snapshot as the target version, as the workspace's
        current version. No prior version is ever modified or
        removed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError:
                If the workspace ID or version is None or blank, no
                version has ever been published for the workspace, or
                the version was never published for it
        """

        self._validate_identifier(workspace_id, "workspace ID")
        self._validate_identifier(version, "version")

        with self._lock:
            history = self._histories.get(workspace_id)

            if history is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                    f"Cannot roll back: no version has ever been published for workspace ID {workspace_id!r}."
                )

            target = self._find_version(history, version)

            if target is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                    f"Cannot roll back: no version {version!r} has been published for workspace ID {workspace_id!r}."
                )

            restored = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion(
                version=str(uuid4()),
                snapshot_id=target.snapshot_id,
                created_at=datetime.now(timezone.utc),
            )

            self._histories[workspace_id] = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionHistory(
                workspace_id=workspace_id,
                current_version=restored.version,
                versions=history.versions + (restored,),
            )

            return restored

    def _existing_versions(self, workspace_id: str) -> tuple:
        history = self._histories.get(workspace_id)

        return history.versions if history is not None else ()

    def _find_version(self, history, version: str):
        for existing in history.versions:
            if existing.version == version:
                return existing

        return None

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                f"Cannot operate with an empty or blank {label}."
            )
