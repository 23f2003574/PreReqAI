from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationResult:
    """
    Immutable outcome produced after instantiating a consumer
    projection execution capability registry event subscription
    lifecycle policy from a template.

    The result is a value object only. It performs no resolution,
    no validation, and no instantiation. Resolution, validation, and
    instantiation are the responsibility of a template instantiation
    service.

    Attributes:
        lifecycle_policy: A newly created lifecycle policy instance,
            independent of the template's own lifecycle policy
        template_id: The identifier of the template the policy was
            instantiated from
        instantiated_at: When the instantiation occurred
    """

    lifecycle_policy: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy
    )

    template_id: str

    instantiated_at: datetime
