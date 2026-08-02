from dataclasses import (
    dataclass,
)

from typing import Mapping


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentResult:
    """
    Immutable outcome produced after atomically deploying a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace into a target runtime
    environment.

    Attributes:
        deployment_id: The deterministic identifier of the
            deployment slot for the workspace
        deployed_resources: An immutable mapping of resource kind
            ("bindings", "templates", "presets", "groups") to an
            immutable, order-preserving tuple of the identifiers of
            that kind of resource deployed as part of this
            deployment
        successful: Whether the deployment completed without error
    """

    deployment_id: str

    deployed_resources: Mapping[str, tuple]

    successful: bool
