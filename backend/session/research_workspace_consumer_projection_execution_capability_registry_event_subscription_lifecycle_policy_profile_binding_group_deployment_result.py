from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentResult:
    """
    Immutable outcome produced after atomically deploying a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding group into a target runtime
    environment.

    Attributes:
        deployment_id: The deterministic identifier of the
            deployment slot for the group
        deployed_bindings: An immutable, order-preserving tuple of the
            identifiers of every member binding deployed as part of
            this deployment
        successful: Whether the deployment completed without error
    """

    deployment_id: str

    deployed_bindings: tuple

    successful: bool
