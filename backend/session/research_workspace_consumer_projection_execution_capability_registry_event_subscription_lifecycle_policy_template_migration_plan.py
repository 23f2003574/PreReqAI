from dataclasses import (
    dataclass,
)

from typing import Callable

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationPlan:
    """
    Immutable, ordered plan describing how to migrate a consumer
    projection execution capability registry event subscription
    lifecycle policy from one template version to another.

    The plan is a value object only. It performs no path discovery
    and no migration. Path discovery and migration are the
    responsibility of a migration service.

    Attributes:
        source_version: The version the plan migrates from
        target_version: The version the plan migrates to
        migration_steps: An immutable, order-preserving tuple of
            single-hop transformations to apply sequentially, each
            taking a lifecycle policy and returning a new one
    """

    source_version: str

    target_version: str

    migration_steps: tuple[
        Callable[
            [
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy
            ],
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
        ],
        ...,
    ]
