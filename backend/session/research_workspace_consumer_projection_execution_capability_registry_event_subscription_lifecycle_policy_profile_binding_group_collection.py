from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCollection:
    """
    Immutable, order-preserving collection of consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding groups.

    The collection is a value object only. It performs no
    registration, no lookup, and no validation of its groups.
    Registration and lookup are the responsibility of a binding
    group service.

    Attributes:
        groups: The groups, in deterministic order
    """

    groups: tuple
