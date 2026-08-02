from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_compatibility_rule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityResult:
    """
    Immutable outcome produced after checking whether every binding,
    binding template, binding preset, and binding group referenced by
    a consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace is
    mutually compatible.

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
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule,
        ...,
    ]
