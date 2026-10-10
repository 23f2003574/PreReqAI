from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReadinessImpact(
    str,
    Enum,
):
    """
    Directional classification of the issue-level change described
    by a readiness transition explanation.
    """

    NONE = (
        "none"
    )

    POSITIVE = (
        "positive"
    )

    NEGATIVE = (
        "negative"
    )

    MIXED = (
        "mixed"
    )
