from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRequest:
    """
    Immutable request to atomically deploy a released version of a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace into a
    target runtime environment, as a single, consistent runtime
    configuration.

    The request is a value object only. It performs no resolution,
    no validation, and no deployment. Resolution, validation, and
    deployment are the responsibility of a deployment service.

    Attributes:
        workspace_id: The identifier of the workspace to deploy
        version: The released workspace version to deploy
        target_environment: The runtime environment to deploy into
    """

    workspace_id: str

    version: str

    target_environment: str

    def __post_init__(self):
        if self.workspace_id is None or not self.workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                "Cannot build a deployment request with an empty or blank workspace ID."
            )

        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                "Cannot build a deployment request with an empty or blank version."
            )

        if self.target_environment is None or not self.target_environment.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                "Cannot build a deployment request with an empty or blank target environment."
            )
