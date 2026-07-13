from enum import Enum


class ResearchSessionStatus(
    str,
    Enum,
):
    """
    Represents the human-managed
    lifecycle state of a research session.
    """

    ACTIVE = "active"

    PAUSED = "paused"

    COMPLETED = "completed"
