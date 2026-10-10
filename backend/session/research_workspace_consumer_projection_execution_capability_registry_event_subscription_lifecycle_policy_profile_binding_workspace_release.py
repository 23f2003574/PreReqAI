from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRelease:
    """
    Immutable record of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace version's position in its controlled release
    lifecycle.

    The release is a value object only. It performs no transition
    logic. Releasing and retiring are the responsibility of a
    release service, which produces a new release record for every
    transition rather than mutating an existing one.

    Attributes:
        release_id: The release record's unique identifier
        workspace_id: The identifier of the workspace the released
            version belongs to
        version: The workspace version this release record applies
            to
        status: The version's current stage in its release lifecycle
        released_at: When the version was first released, or None if
            it has never been released
    """

    release_id: str

    workspace_id: str

    version: str

    status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus
    )

    released_at: (
        datetime | None
    )

    def __post_init__(self):
        if self.release_id is None or not self.release_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                "Cannot build a release with an empty or blank release ID."
            )

        if self.workspace_id is None or not self.workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                "Cannot build a release with an empty or blank workspace ID."
            )

        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                "Cannot build a release with an empty or blank version."
            )

        if not isinstance(
            self.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceReleaseError(
                "Cannot build a release with an invalid status."
            )
