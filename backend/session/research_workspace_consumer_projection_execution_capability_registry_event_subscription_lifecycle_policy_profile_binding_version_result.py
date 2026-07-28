from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionResult:
    """
    Immutable outcome produced after resolving the version a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding currently targets.

    Attributes:
        resolved: Whether a released profile version was resolved
        version: The resolved version identifier, or None if
            resolution failed
    """

    resolved: bool

    version: (
        str | None
    )
