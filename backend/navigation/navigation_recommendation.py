from dataclasses import dataclass

from .navigation_target import (
    NavigationTarget,
)


@dataclass
class NavigationRecommendation:
    """
    Represents one recommended
    navigation destination.
    """

    target: NavigationTarget

    reason: str
