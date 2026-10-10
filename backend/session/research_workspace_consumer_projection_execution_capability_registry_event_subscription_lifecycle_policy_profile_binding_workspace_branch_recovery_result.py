from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_archive_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchRecoveryResult:
    """
    Immutable result of restoring a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace branch from its archive.

    Attributes:
        branch_id: The identifier of the branch that was restored
        recovered: True if the branch was successfully restored
        recovered_at: When the branch was restored, or None if
            recovered is False
    """

    branch_id: str

    recovered: bool

    recovered_at: datetime | None

    def __post_init__(self):
        if self.branch_id is None or not self.branch_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                "Cannot build a branch recovery result with an empty or blank branch ID."
            )

        if not isinstance(self.recovered, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                "Cannot build a branch recovery result: recovered must be a bool."
            )

        if self.recovered and self.recovered_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                "Cannot build a branch recovery result: a recovered result must have a recovered_at."
            )

        if not self.recovered and self.recovered_at is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                "Cannot build a branch recovery result: an unrecovered result cannot have a recovered_at."
            )
