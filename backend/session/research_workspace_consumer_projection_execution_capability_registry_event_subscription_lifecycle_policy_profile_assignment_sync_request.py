from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest:
    """
    Immutable request description for synchronizing an assignment change
    across registries, caches, or nodes.

    Attributes:
        target_id: The identifier of the target capability or subscription.
        profile_id: The identifier of the profile, or None/blank if removing.
        operation: The sync operation ("register" or "remove").
    """

    target_id: str

    profile_id: str | None

    operation: str

    def __post_init__(self):
        if self.target_id is None or not self.target_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError(
                "Cannot build a sync request with an empty or blank target ID."
            )

        if self.operation is None or not self.operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError(
                "Cannot build a sync request with an empty or blank operation."
            )

        if self.operation not in ("register", "remove"):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError(
                f"Invalid sync request operation {self.operation!r}. Must be 'register' or 'remove'."
            )

        if self.operation == "register":
            if self.profile_id is None or not self.profile_id.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError(
                    "Profile ID cannot be empty or blank for a 'register' operation."
                )
