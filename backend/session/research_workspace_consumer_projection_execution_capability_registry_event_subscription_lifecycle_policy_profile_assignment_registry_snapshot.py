from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistrySnapshot:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile assignment
    registry's state at the moment it was taken.

    The snapshot is a value object only. It performs no registration,
    no lookup, and no generation. Generation is the responsibility of
    an assignment registry service.

    Attributes:
        assignment_count: The number of active assignments at the
            moment of the snapshot
        target_ids: An immutable, order-preserving tuple of every
            target identifier with an active assignment at the moment
            of the snapshot
        profile_ids: An immutable, order-preserving tuple of the
            profile identifier of every active assignment at the
            moment of the snapshot, in the same order as target_ids
    """

    assignment_count: int

    target_ids: tuple[
        str,
        ...,
    ]

    profile_ids: tuple[
        str,
        ...,
    ]
