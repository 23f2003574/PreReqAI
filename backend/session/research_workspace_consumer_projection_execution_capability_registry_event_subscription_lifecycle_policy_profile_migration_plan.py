from dataclasses import (
    dataclass,
)

from typing import Callable

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationPlan:
    """
    Immutable, ordered plan describing how to migrate a consumer
    projection execution capability registry event subscription
    lifecycle policy profile from one published version to another.

    The plan is a value object only. It performs no path discovery
    and no migration. Path discovery and migration are the
    responsibility of a migration service.

    Attributes:
        profile_id: The identifier of the profile the plan migrates
        source_version: The version the plan migrates from
        target_version: The version the plan migrates to
        migration_steps: An immutable, order-preserving tuple of
            single-hop transformations to apply sequentially, each
            taking a profile instance and returning a new one. Empty
            when source_version and target_version are identical
    """

    profile_id: str

    source_version: str

    target_version: str

    migration_steps: tuple[
        Callable[
            [
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance
            ],
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
        ],
        ...,
    ]
