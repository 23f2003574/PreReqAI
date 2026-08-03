from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus(
    str,
    Enum,
):
    """
    Canonical states a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace change conflict can be in.

    This enum only names the possible states. It performs no
    resolution logic; a workspace conflict service is responsible for
    enforcing which transitions are valid.

    UNRESOLVED is the only state a conflict may be resolved from.
    RESOLVED is terminal: once reached, a conflict can no longer be
    resolved again.
    """

    UNRESOLVED = "unresolved"

    RESOLVED = "resolved"
