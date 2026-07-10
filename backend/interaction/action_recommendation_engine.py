from .action_recommendation import (
    ActionRecommendation,
)
from .object_action import (
    ObjectAction,
)
from .research_object import (
    ResearchObject,
)


class ActionRecommendationEngine:
    """
    Recommends educational actions based
    on learner interaction history, so a
    learner who already completed an
    action on an object gets nudged
    toward the actions they haven't
    tried yet instead of seeing the same
    static list every time.
    """

    DEFAULT_PRIORITY = [
        ObjectAction.EXPLAIN,
        ObjectAction.VISUALIZE,
        ObjectAction.COMPARE,
        ObjectAction.IMPLEMENT,
        ObjectAction.QUIZ,
    ]

    def recommend(
        self,
        research_object: ResearchObject,
        session,
    ) -> list[ActionRecommendation]:

        available = (
            research_object.available_actions()
        )

        history = getattr(
            session,
            "interaction_history",
            None,
        )

        if history is None:

            return [
                ActionRecommendation(
                    action=action,
                    reason="No interaction history yet",
                )
                for action in self.DEFAULT_PRIORITY
                if action in available
            ]

        return [
            ActionRecommendation(
                action=action,
                reason="Not yet completed for this object",
            )
            for action in self.DEFAULT_PRIORITY
            if action in available
            and not history.has_completed(
                research_object.id,
                action,
            )
        ]
