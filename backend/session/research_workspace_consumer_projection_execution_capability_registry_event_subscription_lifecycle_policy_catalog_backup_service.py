from datetime import (
    datetime,
    timezone,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_backup import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackup,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_backup_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog_recovery_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogRecoveryResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService:
    """
    Creates point-in-time backups of a consumer projection execution
    capability registry event subscription lifecycle policy catalog
    and recovers catalogs from them, independent of any snapshot or
    archive mechanism.

    The service's responsibility is backup creation, recovery, and
    verification, not catalog mutation, evaluation, or
    synchronization. It does NOT build catalogs from scratch, mutate
    catalogs, evaluate policies, execute lifecycle transitions,
    persist backups externally, log, or publish events.

    Unlike the other catalog services in this family, the service
    is not fully stateless: it tracks the backup IDs it has issued,
    since backup ID uniqueness must be enforced across separate
    create_backup() calls and no external backup collection is
    passed in to check against. It never mutates a catalog or
    backup passed to it.
    """

    def __init__(
        self,
    ):

        self._used_backup_ids = set()

    def create_backup(

        self,

        catalog,

        backup_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackup:
        """
        Create a point-in-time backup of a policy catalog.

        Args:
            catalog: The policy catalog to back up
            backup_id: The unique identifier this backup should
                carry

        Returns:
            An immutable backup referencing the catalog exactly as
            given

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError:
                If the catalog or backup ID is None, the backup ID
                is blank, or the backup ID has already been used by
                this service
        """

        if catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError(
                    "Cannot back up a None policy catalog."
                )
            )

        if backup_id is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError(
                    "Cannot back up a policy catalog with a None backup ID."
                )
            )

        if not backup_id:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError(
                    "Cannot back up a policy catalog with a blank backup ID."
                )
            )

        if backup_id in self._used_backup_ids:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError(
                    f"Cannot back up with duplicate backup ID '{backup_id}'."
                )
            )

        backup = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackup(
                backup_id=backup_id,

                catalog=catalog,

                created_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        self._used_backup_ids.add(
            backup_id
        )

        return backup

    def recover(

        self,

        backup,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogRecoveryResult:
        """
        Recover the policy catalog carried by a backup.

        Args:
            backup: The backup to recover from

        Returns:
            An immutable recovery result carrying the exact catalog
            that was backed up

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError:
                If the backup or its catalog is None
        """

        if backup is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError(
                    "Cannot recover from a None backup."
                )
            )

        if backup.catalog is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError(
                    "Cannot recover from a backup with a None catalog."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogRecoveryResult(
                recovered_catalog=backup.catalog,

                backup_id=backup.backup_id,

                recovery_successful=True,
            )
        )

    def verify_backup(

        self,

        backup,

    ) -> bool:
        """
        Verify that a backup's catalog metadata and policies are
        intact.

        Unlike recover(), this method never raises for a
        structurally invalid backup; it reports invalidity as a
        False return value so callers can check backup integrity
        without handling exceptions.

        Args:
            backup: The backup to verify

        Returns:
            True if the backup's catalog has valid metadata and
            every policy has a non-empty identifier and is not None;
            False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError:
                If the backup itself is None
        """

        if backup is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError(
                    "Cannot verify a None backup."
                )
            )

        if backup.catalog is None:

            return False

        if backup.catalog.metadata is None:

            return False

        if backup.catalog.policies is None:

            return False

        for identifier, policy in backup.catalog.policies.items():

            if not identifier:

                return False

            if policy is None:

                return False

        return True
