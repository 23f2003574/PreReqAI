from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_archive_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchive:
    """
    Immutable record of a single occasion a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace branch was archived.

    The archive record is a value object only. It performs no
    archiving or restoring. Those are the responsibility of a binding
    workspace branch archive service, which produces a new archive
    record for every archiving rather than mutating an existing one.

    Attributes:
        archive_id: The archive record's unique identifier
        branch_id: The identifier of the branch that was archived
        archived_at: When the branch was archived
        reason: A human-readable explanation for why the branch was
            archived, or None if none was given
    """

    archive_id: str

    branch_id: str

    archived_at: datetime

    reason: str | None

    def __post_init__(self):
        if self.archive_id is None or not self.archive_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                "Cannot build a branch archive with an empty or blank archive ID."
            )

        if self.branch_id is None or not self.branch_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                "Cannot build a branch archive with an empty or blank branch ID."
            )

        if self.archived_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                "Cannot build a branch archive with a None archived_at."
            )

        if self.reason is not None and not self.reason.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                "Cannot build a branch archive with a blank reason; omit it entirely instead."
            )
