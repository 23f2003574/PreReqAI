from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRecord:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding group deployment, kept for auditing, rollback, and
    operational analysis.

    The record is a value object only. It performs no recording and
    no querying. Recording and querying are the responsibility of a
    deployment history service.

    Attributes:
        deployment_id: The deployment's unique identifier
        group_id: The identifier of the group that was deployed
        version: The group version that was deployed
        environment: The runtime environment the deployment was
            published into
        deployed_at: When the deployment occurred
        status: The outcome of the deployment
    """

    deployment_id: str

    group_id: str

    version: str

    environment: str

    deployed_at: datetime

    status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentStatus
    )
