from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionEligibilityReason(
    str,
    Enum,
):
    """
    A generic, standardized primary cause for a
    projection execution eligibility classification.
    """

    READY = (
        "ready"
    )

    DEGRADED_READY = (
        "degraded_ready"
    )

    BLOCKED = (
        "blocked"
    )

    MANUAL_APPROVAL_REQUIRED = (
        "manual_approval_required"
    )
