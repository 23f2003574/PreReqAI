from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionKind(
    str,
    Enum,
):
    """
    Direction of health movement between two consumer projection
    execution health summaries.

    UNCHANGED means the health classification stayed the same.

    IMPROVED means health improved without reaching HEALTHY
    (currently only CRITICAL -> ATTENTION).

    DETERIORATED means health worsened without newly entering
    CRITICAL (currently only HEALTHY -> ATTENTION).

    RECOVERED means the previous execution had concerns
    (ATTENTION or CRITICAL) and the current execution is HEALTHY -
    more specific than a generic improvement.

    BECAME_CRITICAL means the previous execution was not CRITICAL
    and the current execution is CRITICAL.
    """

    UNCHANGED = (
        "unchanged"
    )

    IMPROVED = (
        "improved"
    )

    DETERIORATED = (
        "deteriorated"
    )

    RECOVERED = (
        "recovered"
    )

    BECAME_CRITICAL = (
        "became_critical"
    )
