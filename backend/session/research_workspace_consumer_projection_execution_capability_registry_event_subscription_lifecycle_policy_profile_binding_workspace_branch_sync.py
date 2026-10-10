from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_sync_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSync:
    """
    Immutable record of a single attempt to synchronize a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace branch with its
    workspace's latest revision.

    The sync record is a value object only. It performs no
    synchronization. Synchronizing a branch, and producing this
    record, is the responsibility of a binding workspace branch
    synchronization service.

    Attributes:
        sync_id: The synchronization attempt's unique identifier
        branch_id: The identifier of the branch that was synchronized
        source_revision: The revision the branch was synchronized
            from, or None if none was known
        target_revision: The revision the branch was synchronized
            onto, or None if its workspace has never had a revision
            published
        status: The synchronization attempt's outcome
    """

    sync_id: str

    branch_id: str

    source_revision: str | None

    target_revision: str | None

    status: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus

    def __post_init__(self):
        if self.sync_id is None or not self.sync_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                "Cannot build a branch sync with an empty or blank sync ID."
            )

        if self.branch_id is None or not self.branch_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                "Cannot build a branch sync with an empty or blank branch ID."
            )

        if self.source_revision is not None and not self.source_revision.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                "Cannot build a branch sync with a blank source revision; omit it entirely instead."
            )

        if self.target_revision is not None and not self.target_revision.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                "Cannot build a branch sync with a blank target revision; omit it entirely instead."
            )

        if not isinstance(
            self.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                "Cannot build a branch sync: status must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus."
            )
