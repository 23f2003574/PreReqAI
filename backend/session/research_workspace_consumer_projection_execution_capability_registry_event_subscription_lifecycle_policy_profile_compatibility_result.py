from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_compatibility_rule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityResult:
    """
    Immutable outcome produced after checking whether a consumer
    projection execution capability registry event subscription
    lifecycle policy profile can safely coexist with registry
    capabilities, deployment targets, and profile versions.

    The result is a value object only. It performs no evaluation.
    Evaluation is the responsibility of a compatibility service.

    Attributes:
        compatible: Whether every ERROR-severity compatibility rule
            passed
        incompatibilities: An immutable, order-preserving tuple of
            every rule that failed, in evaluation order, whether or
            not it was ERROR-severity
    """

    compatible: bool

    incompatibilities: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule,
        ...,
    ]
