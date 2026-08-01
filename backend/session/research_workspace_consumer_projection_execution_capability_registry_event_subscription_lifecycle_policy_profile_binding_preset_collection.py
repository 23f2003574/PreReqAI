from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCollection:
    """
    Immutable, order-preserving collection of consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding presets.

    The collection is a value object only. It performs no
    registration, no lookup, and no instantiation. Registration,
    lookup, and instantiation are the responsibility of a binding
    preset service.

    Attributes:
        presets: The presets, in deterministic order
    """

    presets: tuple
