from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentResult:
    """
    Immutable outcome produced after atomically deploying a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding preset into a target runtime
    environment.

    Attributes:
        deployment_id: The deterministic identifier of the
            deployment slot for the preset
        instantiated_binding_ids: An immutable, order-preserving
            tuple of the identifiers of the independent bindings
            instantiated and activated, across every member binding
            template, as part of this deployment
        successful: Whether the deployment completed without error
    """

    deployment_id: str

    instantiated_binding_ids: tuple

    successful: bool
