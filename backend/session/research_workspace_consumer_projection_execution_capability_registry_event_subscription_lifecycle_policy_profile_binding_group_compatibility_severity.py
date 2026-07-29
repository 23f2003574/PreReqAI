from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCompatibilitySeverity(
    str,
    Enum,
):
    """
    Canonical severities a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    group compatibility rule can be assigned.

    This enum only names the possible severities. It performs no
    evaluation logic. Only a failing ERROR-severity rule makes a
    group overall incompatible; a failing WARNING-severity rule is
    still evaluated and reported.
    """

    ERROR = "error"

    WARNING = "warning"
