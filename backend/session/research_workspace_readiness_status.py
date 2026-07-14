from enum import (
    Enum,
)


class ResearchWorkspaceReadinessStatus(
    str,
    Enum,
):
    """
    Describes the aggregate operational
    readiness of the research workspace.
    """

    READY = (
        "ready"
    )

    DEGRADED = (
        "degraded"
    )

    UNAVAILABLE = (
        "unavailable"
    )
