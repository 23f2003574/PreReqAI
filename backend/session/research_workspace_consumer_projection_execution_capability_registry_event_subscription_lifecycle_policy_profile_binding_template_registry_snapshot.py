from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistrySnapshot:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    template registry's state at the moment it was taken.

    The snapshot is a value object only. It performs no registration,
    no lookup, and no generation. Generation is the responsibility of
    a binding template registry service.

    Attributes:
        template_count: The number of registered templates at the
            moment of the snapshot
        binding_count: The number of distinct binding identifiers
            referenced among the registered templates' members at
            the moment of the snapshot
    """

    template_count: int

    binding_count: int
