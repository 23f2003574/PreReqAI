from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseResult:
    """
    Immutable result of attempting to rebase, or preview rebasing, a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace change
    set onto a newer workspace revision.

    Attributes:
        successful: True if the rebase was, or would be, completed;
            False if it was blocked by unresolved conflicts
        rebased_operations: The change set's operations, in their
            original order, as replayed against the target revision;
            empty if the rebase was unsuccessful
        conflicts: The unresolved conflicts that blocked the rebase;
            empty if the rebase was successful
    """

    successful: bool

    rebased_operations: tuple

    conflicts: tuple
