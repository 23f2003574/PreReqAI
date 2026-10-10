from .next_action_recommendation import (
    NextActionRecommendation,
)

from .next_action_recommendation_list import (
    NextActionRecommendationList,
)


class PersonalizedNextActionPanel:
    """
    Transforms backend recommendations
    into actionable workspace suggestions.
    """

    def __init__(self):

        self.view_model = (
            NextActionRecommendationList()
        )

    def load(

        self,

        recommendations,

    ) -> NextActionRecommendationList:

        items = [

            self._build_recommendation(

                recommendation,

                index,
            )

            for index, recommendation

            in enumerate(
                recommendations
            )
        ]

        items.sort(

            key=lambda item:
                item.priority,

            reverse=True,
        )

        self.view_model = (

            NextActionRecommendationList(

                recommendations=items
            )
        )

        return self.view_model

    def select(

        self,

        recommendation_id: str,

    ):

        selected = next(

            (

                recommendation

                for recommendation

                in self.view_model
                .recommendations

                if (

                    recommendation.id

                    == recommendation_id
                )
            ),

            None,
        )

        self.view_model.selected_recommendation_id = (

            recommendation_id

            if selected

            else None
        )

        return selected

    @staticmethod
    def _build_recommendation(

        recommendation,

        index: int,

    ):

        action = getattr(

            recommendation,

            "action",

            "explore",
        )

        if hasattr(

            action,

            "value",
        ):

            action = action.value

        object_id = getattr(

            recommendation,

            "object_id",

            None,
        )

        title = getattr(

            recommendation,

            "title",

            None,
        )

        if title is None:

            title = (

                str(action)
                .replace("_", " ")
                .title()
            )

        description = getattr(

            recommendation,

            "description",

            None,
        )

        if description is None:

            description = getattr(

                recommendation,

                "reason",

                "",
            )

        return NextActionRecommendation(

            id=str(

                getattr(

                    recommendation,

                    "id",

                    f"recommendation-{index + 1}",
                )
            ),

            title=title,

            description=str(

                description
            ),

            action=str(
                action
            ),

            object_id=object_id,

            priority=int(

                getattr(

                    recommendation,

                    "priority",

                    0,
                )
            ),

            source=recommendation,
        )
