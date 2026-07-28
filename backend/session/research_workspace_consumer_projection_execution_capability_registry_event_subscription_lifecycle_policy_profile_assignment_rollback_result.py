from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRollbackResult:
    """
    Immutable outcome produced after rolling a consumer projection
    execution capability registry event subscription lifecycle
    policy profile assignment target back to a previously recorded
    state.

    Attributes:
        previous_assignment: The assignment that was active
            immediately before the rollback, or None if the target
            was unassigned
        restored_assignment: The assignment restored as active, or
            None if the restored state is unassigned
        successful: Whether the rollback completed without error
    """

    previous_assignment: object

    restored_assignment: object

    successful: bool
