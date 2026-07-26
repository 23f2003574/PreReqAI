from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistrySnapshot:
    """
    Immutable snapshot of a consumer projection execution
    capability registry event subscription lifecycle policy
    profile registry's state at the moment it was taken.

    The snapshot is a value object only. It performs no
    registration, no lookup, and no generation. Generation is the
    responsibility of a profile registry service.

    Attributes:
        profile_count: The number of profiles registered at the
            moment of the snapshot
        profile_identifiers: An immutable, order-preserving tuple of
            every registered profile's identifier at the moment of
            the snapshot
    """

    profile_count: int

    profile_identifiers: tuple[
        str,
        ...,
    ]
