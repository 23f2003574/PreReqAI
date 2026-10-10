from dataclasses import (
    dataclass,
    field,
)

from typing import Any

from .timeline_step_status import (
    TimelineStepStatus,
)


@dataclass
class TimelineStep:
    """
    Represents one visual step inside
    a learning workflow timeline.
    """

    id: str

    title: str

    status: TimelineStepStatus = (
        TimelineStepStatus.PENDING
    )

    source: Any = None

    metadata: dict = field(
        default_factory=dict,
    )
