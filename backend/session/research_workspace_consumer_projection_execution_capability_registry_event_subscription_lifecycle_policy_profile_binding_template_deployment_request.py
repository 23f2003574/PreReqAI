from dataclasses import (
    dataclass,
)

from typing import Any

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRequest:
    """
    Immutable request to atomically deploy a released version of a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding template into a
    target runtime environment, by instantiating and activating all
    of its generated bindings.

    The request is a value object only. It performs no resolution,
    no validation, and no deployment. Resolution, validation, and
    deployment are the responsibility of a deployment service.

    Attributes:
        template_id: The identifier of the template to deploy
        version: The released template version to deploy
        target_environment: The runtime environment to deploy into
        parameter_values: The parameter values to instantiate the
            template's bindings with
    """

    template_id: str

    version: str

    target_environment: str

    parameter_values: Any

    def __post_init__(self):
        if self.template_id is None or not self.template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                "Cannot build a deployment request with an empty or blank template ID."
            )

        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                "Cannot build a deployment request with an empty or blank version."
            )

        if self.target_environment is None or not self.target_environment.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                "Cannot build a deployment request with an empty or blank target environment."
            )
