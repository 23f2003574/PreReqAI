from dataclasses import (
    dataclass,
    field,
)

from typing import Any


@dataclass
class NextActionRecommendation:
    """
    Represents one personalized
    next action suggested inside
    the research workspace.
    """

    id: str

    title: str

    description: str

    action: str

    object_id: str | None = None

    priority: int = 0

    source: Any = None

    metadata: dict = field(
        default_factory=dict,
    )
