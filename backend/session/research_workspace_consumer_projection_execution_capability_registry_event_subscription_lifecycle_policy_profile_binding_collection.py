from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection:
    """
    Immutable, order-preserving collection of consumer projection
    execution capability registry event subscription lifecycle
    policy profile bindings.

    The collection is a value object only. It performs no binding,
    no lookup, and no validation of its bindings. Binding and lookup
    are the responsibility of a binding service.

    Attributes:
        bindings: The bindings, in deterministic order
    """

    bindings: tuple
