from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCollection:
    """
    Immutable, order-preserving collection of consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding templates.

    The collection is a value object only. It performs no
    registration, no lookup, and no instantiation. Registration,
    lookup, and instantiation are the responsibility of a binding
    template service.

    Attributes:
        templates: The templates, in deterministic order
    """

    templates: tuple
