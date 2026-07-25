from dataclasses import (
    dataclass,
)

from datetime import datetime


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy template
    deployment, kept for auditing, rollback decisions, and
    deployment reporting.

    The record is a value object only. It performs no recording and
    no querying. Recording and querying are the responsibility of a
    deployment history service.

    Attributes:
        deployment_id: The deployment's unique identifier
        template_id: The identifier of the template that was
            deployed
        template_version: The version of the template that was
            deployed
        target_registry: The identifier of the registry the
            deployment was published into
        deployed_at: When the deployment occurred
    """

    deployment_id: str

    template_id: str

    template_version: str

    target_registry: str

    deployed_at: datetime
