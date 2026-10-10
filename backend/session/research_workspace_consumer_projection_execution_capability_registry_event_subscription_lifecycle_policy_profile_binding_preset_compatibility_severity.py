from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCompatibilitySeverity(
    str,
    Enum,
):
    """
    Canonical severities a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    preset compatibility rule can be assigned.

    This enum only names the possible severities. It performs no
    evaluation logic. Only a failing ERROR-severity rule makes a
    preset overall incompatible; a failing WARNING-severity rule is
    still evaluated and reported.
    """

    ERROR = "error"

    WARNING = "warning"
