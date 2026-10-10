from dataclasses import dataclass

from .object_action import (
    ObjectAction,
)


@dataclass
class ActionRecommendation:
    """
    Represents one recommended
    educational action.
    """

    action: ObjectAction

    reason: str
