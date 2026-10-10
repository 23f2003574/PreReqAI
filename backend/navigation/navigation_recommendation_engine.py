from .navigation_target import (
    NavigationTarget,
)


class NavigationRecommendationEngine:
    """
    Generates personalized navigation
    recommendations based on the learner's
    exploration history.
    """

    DEFAULT_RECOMMENDATIONS = {

        NavigationTarget.CONCEPT: [

            NavigationTarget.EQUATION,

            NavigationTarget.FIGURE,

            NavigationTarget.EXPERIMENT,
        ],

        NavigationTarget.EQUATION: [

            NavigationTarget.CONCEPT,

            NavigationTarget.FIGURE,
        ],

        NavigationTarget.FIGURE: [

            NavigationTarget.CONCEPT,

            NavigationTarget.EXPERIMENT,
        ],

        NavigationTarget.EXPERIMENT: [

            NavigationTarget.RELATED_PAPER,

            NavigationTarget.REFERENCE,
        ],
    }

    def recommend(

        self,

        history,

    ) -> list[NavigationTarget]:

        if not history.events:

            return [

                NavigationTarget.SECTION,
            ]

        latest = (

            history.events[-1].target
        )

        return self.DEFAULT_RECOMMENDATIONS.get(

            latest,

            [
                NavigationTarget.CONCEPT,
            ],
        )
