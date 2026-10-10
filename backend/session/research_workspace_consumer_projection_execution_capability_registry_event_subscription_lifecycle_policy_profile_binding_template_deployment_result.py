from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentResult:
    """
    Immutable outcome produced after atomically deploying a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding template into a target runtime
    environment.

    Attributes:
        deployment_id: The deterministic identifier of the
            deployment slot for the template
        instantiated_bindings: An immutable, order-preserving tuple
            of the independent binding copies instantiated and
            activated as part of this deployment
        successful: Whether the deployment completed without error
    """

    deployment_id: str

    instantiated_bindings: tuple

    successful: bool
