from backend.navigation import (
    PaperNavigator,
    NavigationRecommendationEngine,
)


class ResearchNavigationPipeline:
    """
    Orchestrates the complete research
    navigation experience: dispatch to the
    right specialized navigator, record
    exploration history, and generate
    personalized recommendations.
    """

    def __init__(self):

        self.navigator = (
            PaperNavigator()
        )

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

            "history":
                session.navigation_history.events,

            "recommendations":
                recommendations,
        }
