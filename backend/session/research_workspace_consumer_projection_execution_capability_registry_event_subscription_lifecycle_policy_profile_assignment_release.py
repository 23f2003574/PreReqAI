from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRelease:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    assignment version's current position in its release lifecycle.

    The release is a value object only. It performs no transition
    logic. Transitions are the responsibility of a release service,
    which produces a new release record for every transition rather
    than mutating an existing one.

    Attributes:
        release_id: The release's unique identifier
        version: The assignment configuration version this release
            record describes
        status: The version's current release status
        released_at: When the version was first released, or None
            if it has never been released
    """

    release_id: str

    version: str

    status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus
    )

    released_at: (
        datetime | None
    )

    def __post_init__(self):
        if self.release_id is None or not self.release_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError(
                "Cannot build a release with an empty or blank release ID."
            )

        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError(
                "Cannot build a release with an empty or blank version."
            )

        if not isinstance(
            self.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentReleaseError(
                "Cannot build a release with an invalid status."
            )
