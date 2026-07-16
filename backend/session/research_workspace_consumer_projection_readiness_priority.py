from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReadinessPriority(
    str,
    Enum,
):
    """
    Relative response priority derived from a readiness
    recommendation.
    """

    NONE = (
        "none"
    )

    LOW = (
        "low"
    )

    MEDIUM = (
        "medium"
    )

    HIGH = (
        "high"
    )

    CRITICAL = (
        "critical"
    )
