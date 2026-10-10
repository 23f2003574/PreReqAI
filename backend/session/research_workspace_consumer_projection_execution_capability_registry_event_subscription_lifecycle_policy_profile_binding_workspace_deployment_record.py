from dataclasses import (
    dataclass,
)

from datetime import datetime

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRecord:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace deployment, kept for auditing, rollback, and
    operational analysis.

    The record is a value object only. It performs no recording and
    no querying. Recording and querying are the responsibility of a
    deployment history service.

    Attributes:
        deployment_id: The deployment's unique identifier
        workspace_id: The identifier of the workspace that was
            deployed
        version: The workspace version that was deployed
        environment: The runtime environment the deployment was
            published into
        deployed_resources: An immutable mapping of resource kind
            ("bindings", "templates", "presets", "groups") to the
            identifiers of that kind of resource deployed as part of
            this deployment
        deployed_at: When the deployment occurred
        status: The outcome of the deployment
    """

    deployment_id: str

    workspace_id: str

    version: str

    environment: str

    deployed_resources: Mapping[str, tuple]

    deployed_at: datetime

    status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentStatus
    )
