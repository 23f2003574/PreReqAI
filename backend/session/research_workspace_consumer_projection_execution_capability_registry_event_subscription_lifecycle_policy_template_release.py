from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRelease:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy
    template version's current position in its release lifecycle.

    The release is a value object only. It performs no transition
    logic. Transitions are the responsibility of a release service,
    which produces a new release record for every transition rather
    than mutating an existing one.

    Attributes:
        template_id: The identifier of the template the version
            belongs to
        version: The template version this release record describes
        status: The version's current release status
        released_at: When the version was first released, or None
            if it has never been released
    """

    template_id: str

    version: str

    status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus
    )

    released_at: (
        datetime | None
    )
