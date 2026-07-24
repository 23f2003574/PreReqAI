from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_catalog import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogRecoveryResult:
    """
    Immutable outcome produced after recovering a consumer projection
    execution capability registry event subscription lifecycle
    policy catalog from a backup.

    The result is a value object only. It performs no recovery, no
    catalog construction, and no verification.

    Attributes:
        recovered_catalog: The catalog exactly as it was backed up
        backup_id: The identifier of the backup recovery was
            performed from
        recovery_successful: Whether the recovery completed
            successfully
    """

    recovered_catalog: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog
    )

    backup_id: str

    recovery_successful: bool
