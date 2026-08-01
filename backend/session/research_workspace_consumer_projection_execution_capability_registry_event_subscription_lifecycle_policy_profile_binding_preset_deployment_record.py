from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRecord:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding preset deployment, kept for auditing, rollback, and
    operational analysis.

    The record is a value object only. It performs no recording and
    no querying. Recording and querying are the responsibility of a
    deployment history service.

    Attributes:
        deployment_id: The deployment's unique identifier
        preset_id: The identifier of the preset that was deployed
        version: The preset version that was deployed
        environment: The runtime environment the deployment was
            published into
        instantiated_binding_ids: The identifiers of the independent
            binding copies instantiated for this deployment, across
            every member binding template, in instantiation order
        deployed_at: When the deployment occurred
        status: The outcome of the deployment
    """

    deployment_id: str

    preset_id: str

    version: str

    environment: str

    instantiated_binding_ids: tuple

    deployed_at: datetime

    status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentStatus
    )
