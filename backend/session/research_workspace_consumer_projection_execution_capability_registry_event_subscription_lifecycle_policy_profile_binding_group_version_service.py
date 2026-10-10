from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_version_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionHistory,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionService:
    """
    Publishes and tracks immutable version snapshots of consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding group membership, so a
    deployment can target a stable snapshot instead of a group's
    mutable, current definition.

    The service's responsibility is version publication, lookup, and
    rollback, not group creation, membership management, deployment,
    or persistence. It does NOT create groups, mutate group
    membership, deploy anything, mutate a published version, persist
    history externally, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two versions published for the same group may
      share a version identifier
    - Append-only: A published version is never replaced or removed;
      a rollback publishes a new version rather than reverting one
    - Chronological: Versions are listed in the order they were
      published
    """

    def __init__(self, group_registry):
        """
        Args:
            group_registry: The registry used to snapshot a group's
                current member bindings at publish time. Any object
                exposing `find(group_id)`, returning an object with a
                `binding_ids` collection, is accepted
        """

        if group_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                "Cannot initialize binding group version service with a None group registry."
            )

        self._group_registry = group_registry
        self._histories = {}
        self._lock = RLock()

    def publish(
        self,
        group_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion:
        """
        Publish a new version snapshot of a group's current member
        bindings.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError:
                If the group ID or version is None or blank, no group
                is registered under the group ID, or the version has
                already been published for the group
        """

        self._validate_identifier(group_id, "group ID")
        self._validate_identifier(version, "version")

        group = self._group_registry.find(group_id)

        if group is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                f"Cannot publish: no group is registered under group ID {group_id!r}."
            )

        with self._lock:
            existing_versions = self._existing_versions(group_id)

            if any(existing.version == version for existing in existing_versions):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                    f"Cannot publish: version {version!r} has already been published for group ID {group_id!r}."
                )

            snapshot = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion(
                version=version,
                binding_ids=tuple(group.binding_ids),
                created_at=datetime.now(timezone.utc),
            )

            self._histories[group_id] = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionHistory(
                group_id=group_id,
                current_version=version,
                versions=existing_versions + (snapshot,),
            )

            return snapshot

    def latest(
        self,
        group_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion:
        """
        Look up a group's currently effective version.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError:
                If the group ID is None or blank, or no version has
                ever been published for the group
        """

        history = self.history(group_id)

        return self._find_version(history, history.current_version)

    def find(self, group_id: str, version: str):
        """
        Find a specific published version of a group.

        Returns:
            The matching version, or None if no version is registered
            under the group ID, or the version was never published
            for it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError:
                If the group ID or version is None or blank
        """

        self._validate_identifier(group_id, "group ID")
        self._validate_identifier(version, "version")

        with self._lock:
            history = self._histories.get(group_id)

        if history is None:
            return None

        return self._find_version(history, version)

    def history(
        self,
        group_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionHistory:
        """
        Get the complete version history of a group.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError:
                If the group ID is None or blank, or no version has
                ever been published for the group
        """

        self._validate_identifier(group_id, "group ID")

        with self._lock:
            history = self._histories.get(group_id)

        if history is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                f"Cannot get history: no version has ever been published for group ID {group_id!r}."
            )

        return history

    def rollback(
        self,
        group_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion:
        """
        Roll a group back to a previously published version.

        The rollback publishes a new version, carrying the same
        member bindings as the target version, as the group's current
        version. No prior version is ever modified or removed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError:
                If the group ID or version is None or blank, no
                version has ever been published for the group, or the
                version was never published for it
        """

        self._validate_identifier(group_id, "group ID")
        self._validate_identifier(version, "version")

        with self._lock:
            history = self._histories.get(group_id)

            if history is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                    f"Cannot roll back: no version has ever been published for group ID {group_id!r}."
                )

            target = self._find_version(history, version)

            if target is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                    f"Cannot roll back: no version {version!r} has been published for group ID {group_id!r}."
                )

            restored = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersion(
                version=str(uuid4()),
                binding_ids=target.binding_ids,
                created_at=datetime.now(timezone.utc),
            )

            self._histories[group_id] = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionHistory(
                group_id=group_id,
                current_version=restored.version,
                versions=history.versions + (restored,),
            )

            return restored

    def _existing_versions(self, group_id: str) -> tuple:
        history = self._histories.get(group_id)

        return history.versions if history is not None else ()

    def _find_version(self, history, version: str):
        for existing in history.versions:
            if existing.version == version:
                return existing

        return None

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionError(
                f"Cannot operate with an empty or blank {label}."
            )
