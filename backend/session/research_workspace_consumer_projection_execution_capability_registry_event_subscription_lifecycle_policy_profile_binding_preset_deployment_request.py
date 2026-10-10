from dataclasses import (
    dataclass,
)

from typing import Any

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRequest:
    """
    Immutable request to atomically deploy a released version of a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding preset into a
    target runtime environment, by instantiating all of its
    referenced binding templates and activating the resulting
    bindings.

    The request is a value object only. It performs no resolution,
    no validation, and no deployment. Resolution, validation, and
    deployment are the responsibility of a deployment service.

    Attributes:
        preset_id: The identifier of the preset to deploy
        version: The released preset version to deploy
        target_environment: The runtime environment to deploy into
        parameter_values: The parameter values to instantiate the
            preset's binding templates with
    """

    preset_id: str

    version: str

    target_environment: str

    parameter_values: Any

    def __post_init__(self):
        if self.preset_id is None or not self.preset_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                "Cannot build a deployment request with an empty or blank preset ID."
            )

        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                "Cannot build a deployment request with an empty or blank version."
            )

        if self.target_environment is None or not self.target_environment.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                "Cannot build a deployment request with an empty or blank target environment."
            )
