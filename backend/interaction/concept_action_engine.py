from .object_action import (
    ObjectAction,
)
from .object_action_engine import (
    ObjectActionEngine,
)


class ConceptActionEngine(ObjectActionEngine):
    """
    Executes educational actions for
    research concepts.
    """

    @staticmethod
    def action_mapping():

        from backend.session import (
            WorkflowType,
        )

        return {
            ObjectAction.EXPLAIN: WorkflowType.EXPLANATION,
            ObjectAction.VISUALIZE: WorkflowType.VISUALIZATION,
            ObjectAction.IMPLEMENT: WorkflowType.IMPLEMENTATION,
            ObjectAction.COMPARE: WorkflowType.COMPARISON,
            ObjectAction.QUIZ: WorkflowType.QUIZ,
        }
