from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistrySnapshot:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    registry's state at the moment it was taken.

    The snapshot is a value object only. It performs no registration,
    no lookup, and no generation. Generation is the responsibility of
    a binding registry service.

    Attributes:
        binding_count: The number of registered bindings at the
            moment of the snapshot
        profile_count: The number of distinct profile identifiers
            represented among the registered bindings at the moment
            of the snapshot
        capability_count: The number of distinct capability
            identifiers represented among the registered bindings at
            the moment of the snapshot
    """

    binding_count: int

    profile_count: int

    capability_count: int
