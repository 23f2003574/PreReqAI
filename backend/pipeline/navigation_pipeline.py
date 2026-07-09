from backend.navigation import (
    PaperNavigator,
    NavigationRecommendationEngine,
)


class NavigationPipeline:
    """
    Orchestrates paper navigation together with
    personalized recommendations for what to
    explore next.
    """

    def __init__(self):

        self.navigator = PaperNavigator()

        self.recommendation_engine = (
            NavigationRecommendationEngine()
        )

    def navigate(

        self,

        session,

        paper,

        target,

        query,

    ):

        result = self.navigator.navigate(
            paper,
            target,
            query,
            session,
        )

        recommendations = (
            self.recommendation_engine.recommend(
                session.navigation_history,
            )
        )

        return {

            "navigation": result,

            "recommendations":
                recommendations,
        }
