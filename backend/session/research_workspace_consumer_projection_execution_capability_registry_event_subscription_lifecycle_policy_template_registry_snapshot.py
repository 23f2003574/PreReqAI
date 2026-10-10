from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistrySnapshot:
    """
    Immutable snapshot of a consumer projection execution
    capability registry event subscription lifecycle policy
    template registry's state at the moment it was taken.

    The snapshot is a value object only. It performs no
    registration, no lookup, and no generation. Generation is the
    responsibility of a template registry service.

    Attributes:
        template_count: The number of templates registered at the
            moment of the snapshot
        template_identifiers: An immutable, order-preserving tuple
            of every registered template's identifier at the moment
            of the snapshot
    """

    template_count: int

    template_identifiers: tuple[
        str,
        ...,
    ]
