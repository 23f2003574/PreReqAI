from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistrySnapshot:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    group registry's state at the moment it was taken.

    The snapshot is a value object only. It performs no registration,
    no lookup, and no generation. Generation is the responsibility of
    a binding group registry service.

    Attributes:
        group_count: The number of registered groups at the moment of
            the snapshot
        binding_count: The number of distinct binding identifiers
            referenced among the registered groups' members at the
            moment of the snapshot
    """

    group_count: int

    binding_count: int
