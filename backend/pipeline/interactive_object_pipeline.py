"""
Lower-level execution layer beneath
InteractiveResearchEngine: dispatches a
single action and returns a standardized
response, with no awareness of multi-action
plans (that's InteractionOrchestrator's job).
"""

from backend.interaction import (
    ActionRecommendationEngine,
    InteractionDispatcher,
)


class InteractiveObjectPipeline:
    """
    Executes educational interactions
    for every research object through
    one unified pipeline.
    """

    def __init__(self, workflow_router=None):

        self.dispatcher = (
            InteractionDispatcher(
                workflow_router,
            )
        )

        self.recommendations = (
            ActionRecommendationEngine()
        )

    def execute(
        self,
        session,
        research_object,
        action,
    ):

        result = self.dispatcher.dispatch(
            research_object,
            action,
            session,
            session.paper,
        )

        recommendations = (
            self.recommendations.recommend(
                research_object,
                session,
            )
        )

        return {

            "interaction":
                result,

            "recommendations":
                recommendations,

            "history_size":
                len(
                    session
                    .interaction_history
                    .events
                ),
        }
