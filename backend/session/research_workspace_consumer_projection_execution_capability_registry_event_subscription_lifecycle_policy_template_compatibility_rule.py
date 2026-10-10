from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule:
    """
    Immutable description of a single named rule a consumer
    projection execution capability registry event subscription
    lifecycle policy template is checked against for compatibility
    with an existing lifecycle policy.

    The rule is a value object only. It performs no evaluation.
    Evaluation is the responsibility of a compatibility service,
    which recognizes a fixed set of well-known rule names.

    Attributes:
        rule_name: The rule's unique, well-known name
        required: Whether this rule must pass for a template to be
            considered compatible. A rule that is not required is
            still evaluated and reported, but does not by itself
            make a template incompatible
    """

    rule_name: str

    required: bool
