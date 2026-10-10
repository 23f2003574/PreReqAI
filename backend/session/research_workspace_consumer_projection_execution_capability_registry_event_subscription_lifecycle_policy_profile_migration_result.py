from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationResult:
    """
    Immutable outcome produced after migrating a consumer projection
    execution capability registry event subscription lifecycle
    policy profile from one published version to another.

    The result is a value object only. It performs no path
    discovery and no migration. Path discovery and migration are the
    responsibility of a migration service.

    Attributes:
        source_version: The version the migration started from
        target_version: The version the migration produced
        migrated_profile: A new profile instance carrying the result
            of the migration, independent of the source version and
            of any historical version
        successful: Whether every migration step applied without
            error
    """

    source_version: str

    target_version: str

    migrated_profile: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance
    )

    successful: bool
