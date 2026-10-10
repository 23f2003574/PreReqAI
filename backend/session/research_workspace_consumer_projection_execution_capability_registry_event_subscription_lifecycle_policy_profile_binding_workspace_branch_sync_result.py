from dataclasses import (
    dataclass,
)

from datetime import datetime


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncResult:
    """
    Immutable result of attempting to synchronize, or preview
    synchronizing, a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace branch with its workspace's latest revision.

    Attributes:
        synchronized: True if the branch was, or would be,
            synchronized; False if it was blocked by unresolved
            conflicts
        conflicts: The unresolved conflicts that blocked
            synchronization; empty if synchronized is True
        synchronized_at: When the branch was actually synchronized, or
            None if this is a preview or synchronization was blocked
    """

    synchronized: bool

    conflicts: tuple

    synchronized_at: datetime | None
