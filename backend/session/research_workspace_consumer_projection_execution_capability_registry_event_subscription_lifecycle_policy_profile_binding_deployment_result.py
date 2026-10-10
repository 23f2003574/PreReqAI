from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentResult:
    """
    Immutable outcome produced after deploying a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding into a target runtime environment.

    Attributes:
        deployment_id: The deterministic identifier of the
            deployment slot for the binding
        binding_id: The identifier of the binding that was deployed
        deployed_version: The profile version that was deployed
        successful: Whether the deployment completed without error
    """

    deployment_id: str

    binding_id: str

    deployed_version: str

    successful: bool
