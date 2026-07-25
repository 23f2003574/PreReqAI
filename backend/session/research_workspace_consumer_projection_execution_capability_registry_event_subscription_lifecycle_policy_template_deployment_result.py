from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentResult:
    """
    Immutable outcome produced after deploying a consumer projection
    execution capability registry event subscription lifecycle
    policy template into a runtime registry.

    The result is a value object only. It performs no resolution,
    no validation, and no deployment. Resolution, validation, and
    deployment are the responsibility of a deployment service.

    Attributes:
        deployed_policy: A new lifecycle policy instance published
            into the target registry, independent of the template's
            own lifecycle policy
        template_id: The identifier of the template that was
            deployed
        deployment_successful: Whether the deployment completed
            without error
        deployed_at: When the deployment occurred
    """

    deployed_policy: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy
    )

    template_id: str

    deployment_successful: bool

    deployed_at: datetime
