from backend.session import (
    LearningRecommendation,
    LearningSession,
    TutorMode,
)


class AdaptiveRecommendationEngine:
    """
    Generates personalized recommendations
    from detected learning gaps.
    """

    def recommend(
        self,
        session: LearningSession,
    ):

        recommendations = []

        for gap in session.learning_gaps:

            if gap.mastery >= 0.8:

                continue

            if gap.mastery >= 0.6:

                mode = TutorMode.ANALOGY

                priority = "Medium"

            elif gap.mastery >= 0.4:

                mode = TutorMode.INTUITION

                priority = "High"

            else:

                mode = TutorMode.PREREQUISITES

                priority = "Critical"

            recommendations.append(

                LearningRecommendation(

                    concept=gap.concept,

                    priority=priority,

                    recommendation=(
                        f"Review {gap.concept} "
                        "before continuing."
                    ),

                    suggested_mode=mode,
                )
            )

        session.recommendations = recommendations

        return recommendations
