from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus(
    str,
    Enum,
):
    """
    Canonical lifecycle states a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace change set can be in.

    This enum only names the possible states. It performs no
    transition logic; a change set service is responsible for
    enforcing which transitions are valid.

    OPEN is the only state in which operations may be staged onto a
    change set or the change set may be applied or discarded. APPLIED
    and DISCARDED are terminal: once reached, a change set can no
    longer be mutated, applied, or discarded again.
    """

    OPEN = "open"

    APPLIED = "applied"

    DISCARDED = "discarded"
