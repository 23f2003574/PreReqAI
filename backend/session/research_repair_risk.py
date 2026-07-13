from enum import (
    Enum,
)


class ResearchRepairRisk(
    str,
    Enum,
):
    """
    Describes the potential destructive
    impact of a proposed repair.
    """

    SAFE = (
        "safe"
    )

    REVIEW = (
        "review"
    )

    DESTRUCTIVE = (
        "destructive"
    )
