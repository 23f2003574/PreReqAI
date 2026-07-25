from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationResult:
    """
    Immutable outcome produced after migrating a consumer projection
    execution capability registry event subscription lifecycle
    policy from one template version to another.

    The result is a value object only. It performs no path
    discovery and no migration. Path discovery and migration are the
    responsibility of a migration service.

    Attributes:
        migrated_policy: A new lifecycle policy instance carrying
            the result of the migration, independent of the source
            policy
        source_version: The version the migration started from
        target_version: The version the migration produced
        migration_successful: Whether every migration step applied
            without error
    """

    migrated_policy: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy
    )

    source_version: str

    target_version: str

    migration_successful: bool
