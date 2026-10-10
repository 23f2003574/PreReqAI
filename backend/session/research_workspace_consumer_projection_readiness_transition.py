from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReadinessTransition(
    str,
    Enum,
):
    """
    Classifies the direction of readiness movement
    between two evaluations of the same projection.

    Severity ordering: READY < DEGRADED_READY < BLOCKED.
    """

    UNCHANGED = (
        "unchanged"
    )

    IMPROVED = (
        "improved"
    )

    DEGRADED = (
        "degraded"
    )

    BLOCKED = (
        "blocked"
    )

    RECOVERED = (
        "recovered"
    )
