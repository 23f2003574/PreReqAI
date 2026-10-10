from enum import Enum


class TimelineStepStatus(str, Enum):
    """
    Represents the execution state
    of a learning timeline step.
    """

    PENDING = "pending"

    ACTIVE = "active"

    COMPLETED = "completed"

    FAILED = "failed"

    SKIPPED = "skipped"
