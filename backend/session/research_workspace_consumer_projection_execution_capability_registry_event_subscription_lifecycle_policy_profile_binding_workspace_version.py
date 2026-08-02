from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersion:
    """
    Immutable pointer to a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace's snapshot at the moment it was published, so a review
    or deployment can target a stable revision instead of the
    workspace's mutable, current definition.

    The version is a value object only. It performs no publication,
    lookup, or rollback. Publication, lookup, and rollback are the
    responsibility of a binding workspace version service.

    Attributes:
        version: The version's unique identifier
        snapshot_id: The identifier of the immutable workspace
            snapshot captured when this version was published
        created_at: When this version was published
    """

    version: str

    snapshot_id: str

    created_at: datetime

    def __post_init__(self):
        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                "Cannot build a workspace version with an empty or blank version."
            )

        if self.snapshot_id is None or not self.snapshot_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                "Cannot build a workspace version with an empty or blank snapshot ID."
            )

        if self.created_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError(
                "Cannot build a workspace version with a None created_at timestamp."
            )
