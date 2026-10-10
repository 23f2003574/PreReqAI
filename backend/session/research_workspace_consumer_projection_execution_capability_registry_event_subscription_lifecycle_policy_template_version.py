from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy template's
    lifecycle policy at a single published version.

    The version is a value object only. It performs no publication,
    no history tracking, and no rollback. Publication and history
    tracking are the responsibility of a template version service.

    Attributes:
        version: The published version identifier
        lifecycle_policy: The lifecycle policy published under this
            version
        created_at: When this version was published
    """

    version: str

    lifecycle_policy: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy
    )

    created_at: datetime
