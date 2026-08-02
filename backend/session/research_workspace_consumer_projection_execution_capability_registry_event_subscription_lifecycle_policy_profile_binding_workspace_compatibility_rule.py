from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_compatibility_severity import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilityRule:
    """
    Immutable description of a single named rule a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace is checked against for
    internal compatibility among its referenced bindings, binding
    templates, binding presets, and binding groups.

    The rule is a value object only. It performs no evaluation.
    Evaluation is the responsibility of a compatibility service,
    which recognizes a fixed set of well-known rule identifiers.

    Attributes:
        rule_id: The rule's unique, well-known identifier
        severity: Whether a failing rule makes the workspace overall
            incompatible (ERROR), or is merely reported (WARNING)
    """

    rule_id: str

    severity: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceCompatibilitySeverity
    )
