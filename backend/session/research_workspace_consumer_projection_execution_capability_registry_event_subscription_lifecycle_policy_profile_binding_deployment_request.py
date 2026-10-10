from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest:
    """
    Immutable request to deploy a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding into a target runtime environment.

    The request is a value object only. It performs no resolution,
    no validation, and no deployment. Resolution, validation, and
    deployment are the responsibility of a deployment service.

    Attributes:
        binding_id: The identifier of the binding to deploy
        target_environment: The runtime environment to deploy into
        version: The specific profile version to deploy, or None to
            resolve the binding's currently selected version
    """

    binding_id: str

    target_environment: str

    version: (
        str | None
    )

    def __post_init__(self):
        if self.binding_id is None or not self.binding_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                "Cannot build a deployment request with an empty or blank binding ID."
            )

        if self.target_environment is None or not self.target_environment.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                "Cannot build a deployment request with an empty or blank target environment."
            )

        if self.version is not None and not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                "Cannot build a deployment request with a blank version."
            )
