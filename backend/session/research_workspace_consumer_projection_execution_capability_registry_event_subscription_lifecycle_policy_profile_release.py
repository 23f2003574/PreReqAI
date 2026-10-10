from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRelease:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    version's current position in its release lifecycle.

    The release is a value object only. It performs no transition
    logic. Transitions are the responsibility of a release service,
    which produces a new release record for every transition rather
    than mutating an existing one.

    Attributes:
        profile_id: The identifier of the profile the version
            belongs to
        version: The profile version this release record describes
        status: The version's current release status
        released_at: When the version was first released, or None
            if it has never been released
    """

    profile_id: str

    version: str

    status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus
    )

    released_at: (
        datetime | None
    )
