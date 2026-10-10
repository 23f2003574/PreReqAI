from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate:
    """
    Immutable, reusable description of a consumer projection
    execution capability registry event subscription lifecycle
    policy, addressed by a template identifier.

    The template is a value object only. It performs no
    registration, no lookup, and no instantiation of the lifecycle
    policies it describes. Registration and lookup are the
    responsibility of a template service; instantiation produces a
    new, independent lifecycle policy instance.

    Attributes:
        template_id: The template's unique identifier
        template_name: The template's human-readable name
        description: A human-readable description of the template
        lifecycle_policy: The lifecycle policy this template
            instantiates
    """

    template_id: str

    template_name: str

    description: str

    lifecycle_policy: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy
    )
