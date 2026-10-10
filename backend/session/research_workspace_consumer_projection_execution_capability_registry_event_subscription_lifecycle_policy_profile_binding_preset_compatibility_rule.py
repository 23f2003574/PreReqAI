from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_compatibility_severity import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilityRule:
    """
    Immutable description of a single named rule a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding preset is checked against for
    compatibility among its referenced binding templates and
    declared parameter definitions.

    The rule is a value object only. It performs no evaluation.
    Evaluation is the responsibility of a compatibility service,
    which recognizes a fixed set of well-known rule identifiers.

    Attributes:
        rule_id: The rule's unique, well-known identifier
        severity: Whether a failing rule makes the preset overall
            incompatible (ERROR), or is merely reported (WARNING)
    """

    rule_id: str

    severity: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity
    )
