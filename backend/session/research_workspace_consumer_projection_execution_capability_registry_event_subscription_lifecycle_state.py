from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState(
    str,
    Enum,
):
    """
    Canonical lifecycle states a consumer projection execution
    capability registry event subscription may occupy.

    This enum only names the possible states. It performs no
    activation, suspension, unregistration, or transition logic.
    """

    REGISTERED = (
        "registered"
    )

    ACTIVE = (
        "active"
    )

    SUSPENDED = (
        "suspended"
    )

    UNREGISTERED = (
        "unregistered"
    )
