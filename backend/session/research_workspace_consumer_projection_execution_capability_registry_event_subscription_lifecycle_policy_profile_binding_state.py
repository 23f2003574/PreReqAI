from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState(
    str,
    Enum,
):
    """
    Activation states a consumer projection execution capability
    registry event subscription lifecycle policy profile binding may
    occupy.

    This enum only names the possible states. It performs no
    transition validation or execution. A binding implicitly starts
    INACTIVE until an activation service activates, deactivates, or
    schedules it. Only an ACTIVE binding participates in resolution.
    """

    ACTIVE = "active"

    INACTIVE = "inactive"

    SCHEDULED = "scheduled"
