from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult:
    """
    Immutable result containing the outcomes of a synchronization execution.

    Attributes:
        synchronized: True if any changes were actually applied during the operation,
            False if everything was already in sync and skipped.
        synchronized_targets: An immutable tuple of target IDs that were successfully synchronized.
    """

    synchronized: bool

    synchronized_targets: tuple[
        str,
        ...,
    ]
