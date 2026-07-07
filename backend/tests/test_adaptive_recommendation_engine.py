from backend.session import (
    LearningSession,
)

from backend.tutor import (
    AdaptiveRecommendationEngine,
    LearningGap,
)


def test_adaptive_recommendations():

    session = LearningSession()

    session.learning_gaps = [

        LearningGap(

            concept="Attention",

            incorrect_attempts=4,

            mastery=0.2,
        )
    ]

    recommendations = (

        AdaptiveRecommendationEngine()
        .recommend(session)
    )

    assert len(
        recommendations
    ) == 1

    assert (

        recommendations[0].priority

        == "Critical"
    )
