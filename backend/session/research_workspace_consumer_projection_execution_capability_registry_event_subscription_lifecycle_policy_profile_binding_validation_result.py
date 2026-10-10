from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationViolation,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationResult:
    """
    Immutable outcome produced after validating a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding, registry, or resolution result.

    The result is a value object only. It performs no validation and
    no accumulation. Validation and accumulation are the
    responsibility of a binding validator.

    Attributes:
        valid: Whether validation found no violations
        violations: An immutable, order-preserving tuple of every
            violation found, empty if the subject is valid
    """

    valid: bool

    violations: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingValidationViolation,
        ...,
    ]
