from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReadinessReasonCode(
    str,
    Enum,
):
    """
    Compact reason code explaining a readiness rationale, resolved
    directly from a readiness operational assessment.
    """

    READY = (
        "ready"
    )

    IMPROVING = (
        "improving"
    )

    RECOVERED = (
        "recovered"
    )

    MIXED = (
        "mixed"
    )

    DETERIORATING = (
        "deteriorating"
    )

    BLOCKED = (
        "blocked"
    )
