from .object_action import (
    ObjectAction,
)
from .object_action_engine import (
    ObjectActionEngine,
)


class FigureActionEngine(ObjectActionEngine):
    """
    Executes educational actions for
    research figures.
    """

    def action_mapping(self):

        from backend.session import (
            WorkflowType,
        )

        return {
            ObjectAction.EXPLAIN: WorkflowType.EXPLANATION,
            ObjectAction.VISUALIZE: WorkflowType.VISUALIZATION,
            ObjectAction.SHOW_RELATIONS: WorkflowType.PREREQUISITE,
        }
