from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus(
    str,
    Enum,
):
    """
    Canonical states a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace branch can be in.

    This enum only names the possible states. It performs no
    transition logic; a workspace branch service is responsible for
    enforcing which transitions are valid.

    OPEN is a branch that exists but is not the workspace's currently
    checked out branch. ACTIVE is the single branch, per workspace,
    currently checked out. CLOSED is terminal: once reached, a branch
    is read-only and can no longer be checked out, renamed, or closed
    again.
    """

    OPEN = "open"

    ACTIVE = "active"

    CLOSED = "closed"
