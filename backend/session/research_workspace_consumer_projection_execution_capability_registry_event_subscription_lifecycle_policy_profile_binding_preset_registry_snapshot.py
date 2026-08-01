from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistrySnapshot:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    preset registry's state at the moment it was taken.

    The snapshot is a value object only. It performs no registration,
    no lookup, and no generation. Generation is the responsibility of
    a binding preset registry service.

    Attributes:
        preset_count: The number of registered presets at the moment
            of the snapshot
        template_count: The number of distinct binding template
            identifiers referenced among the registered presets'
            members at the moment of the snapshot
    """

    preset_count: int

    template_count: int
