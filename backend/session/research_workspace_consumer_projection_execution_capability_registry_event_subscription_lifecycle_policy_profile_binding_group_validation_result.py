from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationViolation,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationResult:
    """
    Immutable outcome produced after validating a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding group, registry, or resolution result.

    The result is a value object only. It performs no validation and
    no accumulation. Validation and accumulation are the
    responsibility of a binding group validator.

    Attributes:
        valid: Whether validation found no violations
        violations: An immutable, order-preserving tuple of every
            violation found, empty if the subject is valid
    """

    valid: bool

    violations: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupValidationViolation,
        ...,
    ]
