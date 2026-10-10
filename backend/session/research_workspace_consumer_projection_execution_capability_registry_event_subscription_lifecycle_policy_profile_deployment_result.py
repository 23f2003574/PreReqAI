from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_instance import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentResult:
    """
    Immutable outcome produced after deploying a consumer projection
    execution capability registry event subscription lifecycle
    policy profile version into a target runtime environment.

    The result is a value object only. It performs no resolution,
    no validation, and no deployment. Resolution, validation, and
    deployment are the responsibility of a deployment service.

    Attributes:
        deployment_id: The deterministic identifier of the
            deployment slot for the profile and target environment
        deployed_profile: A new profile instance published into the
            target environment, independent of the profile's stored
            definition
        target_environment: The runtime environment the profile was
            deployed into
        deployed_at: When the deployment occurred
        successful: Whether the deployment completed without error
    """

    deployment_id: str

    deployed_profile: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance
    )

    target_environment: str

    deployed_at: datetime

    successful: bool
