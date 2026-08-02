from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult:
    """
    Immutable result containing the outcome of a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace synchronization execution.

    Attributes:
        synchronized: True if any changes were actually applied
            during the operation, False if everything was already in
            sync and skipped
        synchronized_targets: An immutable, order-preserving tuple of
            target identifiers that were successfully synchronized
        failed_targets: An immutable, order-preserving tuple of
            target identifiers that were attempted but failed to
            synchronize, and remain eligible for retry
    """

    synchronized: bool

    synchronized_targets: tuple[
        str,
        ...,
    ]

    failed_targets: tuple[
        str,
        ...,
    ]
