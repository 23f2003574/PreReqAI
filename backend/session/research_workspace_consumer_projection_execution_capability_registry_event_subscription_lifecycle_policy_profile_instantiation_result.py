from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationResult:
    """
    Immutable outcome produced after instantiating a consumer
    projection execution capability registry event subscription
    lifecycle policy profile instance from a registered profile
    definition.

    The result is a value object only. It performs no resolution,
    no validation, and no instantiation. Resolution, validation, and
    instantiation are the responsibility of a profile instantiation
    service.

    Attributes:
        profile_instance: A newly created profile instance,
            independent of the stored profile definition
        instantiated: Whether the instance was successfully created
        instantiated_at: When the instantiation occurred
    """

    profile_instance: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance
    )

    instantiated: bool

    instantiated_at: datetime
