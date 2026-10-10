from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRequest:
    """
    Immutable request to atomically deploy a published version of a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding group into a
    target runtime environment.

    The request is a value object only. It performs no resolution,
    no validation, and no deployment. Resolution, validation, and
    deployment are the responsibility of a deployment service.

    Attributes:
        group_id: The identifier of the group to deploy
        version: The published group version to deploy
        target_environment: The runtime environment to deploy into
    """

    group_id: str

    version: str

    target_environment: str

    def __post_init__(self):
        if self.group_id is None or not self.group_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                "Cannot build a deployment request with an empty or blank group ID."
            )

        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                "Cannot build a deployment request with an empty or blank version."
            )

        if self.target_environment is None or not self.target_environment.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                "Cannot build a deployment request with an empty or blank target environment."
            )
