from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus(
    str,
    Enum,
):
    """
    Canonical lifecycle states a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session can occupy.

    This enum only names the possible states. It performs no
    transition logic.
    """

    ACTIVE = "active"

    FINISHED = "finished"

    CANCELLED = "cancelled"
