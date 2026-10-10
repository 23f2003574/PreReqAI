from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_compatibility_rule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityResult:
    """
    Immutable outcome produced after checking whether every binding
    template and parameter definition referenced by a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding preset is mutually compatible.

    The result is a value object only. It performs no evaluation.
    Evaluation is the responsibility of a compatibility service.

    Attributes:
        compatible: Whether every ERROR-severity compatibility rule
            passed
        violations: An immutable, order-preserving tuple of every
            rule that failed, in evaluation order, whether or not it
            was ERROR-severity
    """

    compatible: bool

    violations: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule,
        ...,
    ]
