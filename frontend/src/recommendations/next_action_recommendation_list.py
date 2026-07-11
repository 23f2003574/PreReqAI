from dataclasses import (
    dataclass,
    field,
)

from .next_action_recommendation import (
    NextActionRecommendation,
)


@dataclass
class NextActionRecommendationList:
    """
    Represents the current personalized
    recommendations shown to the learner.
    """

    recommendations: list[
        NextActionRecommendation
    ] = field(
        default_factory=list,
    )

    selected_recommendation_id: (
        str | None
    ) = None
