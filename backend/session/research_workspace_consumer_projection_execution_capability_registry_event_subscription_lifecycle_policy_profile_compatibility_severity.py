from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilitySeverity(
    str,
    Enum,
):
    """
    Canonical severities a consumer projection execution capability
    registry event subscription lifecycle policy profile
    compatibility rule can be assigned.

    This enum only names the possible severities. It performs no
    evaluation logic. Only a failing ERROR-severity rule makes a
    profile overall incompatible; a failing WARNING-severity rule is
    still evaluated and reported.
    """

    ERROR = (
        "error"
    )

    WARNING = (
        "warning"
    )
