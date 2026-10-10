from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityResult:
    """
    Immutable outcome produced after checking whether a consumer
    projection execution capability registry event subscription
    lifecycle policy template can safely instantiate or replace an
    existing lifecycle policy.

    The result is a value object only. It performs no evaluation.
    Evaluation is the responsibility of a compatibility service.

    Attributes:
        compatible: Whether every required compatibility rule passed
        incompatible_fields: An immutable, order-preserving tuple of
            the rule names that failed, whether or not they were
            required
        reason: A human-readable summary of why the template is
            incompatible, or None if it is compatible
    """

    compatible: bool

    incompatible_fields: tuple[
        str,
        ...,
    ]

    reason: (
        str | None
    )
