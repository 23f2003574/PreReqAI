from .action_recommendation import (
    ActionRecommendation,
)
from .object_action import (
    ObjectAction,
)
from .research_object import (
    ResearchObject,
)
from .research_object_type import (
    ResearchObjectType,
)
from .concept_action_engine import (
    ConceptActionEngine,
)
from .equation_action_engine import (
    EquationActionEngine,
)
from .figure_action_engine import (
    FigureActionEngine,
)
from .experiment_action_engine import (
    ExperimentActionEngine,
)
from .reference_action_engine import (
    ReferenceActionEngine,
)

ENGINE_BY_TYPE = {
    ResearchObjectType.CONCEPT: ConceptActionEngine,
    ResearchObjectType.EQUATION: EquationActionEngine,
    ResearchObjectType.FIGURE: FigureActionEngine,
    ResearchObjectType.EXPERIMENT: ExperimentActionEngine,
    ResearchObjectType.REFERENCE: ReferenceActionEngine,
}


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

        workflow_memory = getattr(
            session,
            "workflow_memory",
            None,
        )

        if workflow_memory is None:

            return [
                ActionRecommendation(
                    action=action,
                    reason="No interaction history yet",
                )
                for action in self.DEFAULT_PRIORITY
                if action in available
            ]

        engine_cls = ENGINE_BY_TYPE.get(
            research_object.object_type,
        )

        action_mapping = (
            engine_cls.action_mapping()
            if engine_cls
            else {}
        )

        recommendations = []

        for action in self.DEFAULT_PRIORITY:

            if action not in available:

                continue

            workflow = action_mapping.get(
                action,
            )

            if (
                workflow is not None
                and workflow_memory.has_completed(
                    workflow,
                    research_object.title,
                )
            ):

                continue

            recommendations.append(
                ActionRecommendation(
                    action=action,
                    reason="Not yet completed for this object",
                )
            )

        return recommendations
