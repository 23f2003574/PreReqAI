from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistory:
    """
    Immutable, chronologically ordered collection of every consumer
    projection execution capability registry event subscription
    lifecycle policy template deployment ever recorded.

    The history is a value object only. It performs no recording and
    no querying. Recording and querying are the responsibility of a
    deployment history service.

    Attributes:
        records: An immutable, order-preserving tuple of every
            deployment record, in the order they were recorded
    """

    records: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord,
        ...,
    ]
