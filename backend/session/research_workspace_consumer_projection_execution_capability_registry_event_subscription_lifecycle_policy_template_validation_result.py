from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_validation_violation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationViolation,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationResult:
    """
    Immutable outcome produced after validating a consumer
    projection execution capability registry event subscription
    lifecycle policy template, version, or version history.

    The result is a value object only. It performs no validation
    and no accumulation. Validation and accumulation are the
    responsibility of a template validator.

    Attributes:
        valid: Whether validation found no violations
        violations: An immutable, order-preserving tuple of every
            violation found, empty if the subject is valid
    """

    valid: bool

    violations: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationViolation,
        ...,
    ]
