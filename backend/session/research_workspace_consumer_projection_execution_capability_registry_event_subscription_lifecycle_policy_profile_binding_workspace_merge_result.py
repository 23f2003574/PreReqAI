from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeResult:
    """
    Immutable result of attempting to merge, or preview merging,
    multiple consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace change
    sets.

    Attributes:
        successful: True if the merge was, or would be, completed;
            False if it was blocked by unresolved conflicts
        merged_operations: The operations that were, or would be,
            staged onto the consolidated change set, in order; empty
            if the merge was unsuccessful
        conflicts_detected: The unresolved conflicts that blocked the
            merge; empty if the merge was successful
    """

    successful: bool

    merged_operations: tuple

    conflicts_detected: tuple
