from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReadinessAssessment(
    str,
    Enum,
):
    """
    Compact operational classification combining a readiness
    transition with its issue-level impact.
    """

    STABLE = (
        "stable"
    )

    IMPROVING = (
        "improving"
    )

    RECOVERED = (
        "recovered"
    )

    DETERIORATING = (
        "deteriorating"
    )

    BLOCKED = (
        "blocked"
    )

    MIXED = (
        "mixed"
    )
