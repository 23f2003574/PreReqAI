from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_compatibility_severity import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityRule:
    """
    Immutable description of a single named rule a consumer
    projection execution capability registry event subscription
    lifecycle policy profile is checked against for compatibility
    with registry capabilities, deployment targets, and profile
    versions.

    The rule is a value object only. It performs no evaluation.
    Evaluation is the responsibility of a compatibility service,
    which recognizes a fixed set of well-known rule identifiers.

    Attributes:
        rule_id: The rule's unique, well-known identifier
        description: A human-readable description of what the rule
            checks
        severity: Whether a failing rule makes the profile overall
            incompatible (ERROR), or is merely reported (WARNING)
    """

    rule_id: str

    description: str

    severity: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity
    )
