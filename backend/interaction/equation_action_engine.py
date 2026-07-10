from .object_action import (
    ObjectAction,
)
from .object_action_engine import (
    ObjectActionEngine,
)


class EquationActionEngine(ObjectActionEngine):
    """
    Executes educational actions for
    mathematical equations.
    """

    def action_mapping(self):

        from backend.session import (
            WorkflowType,
        )

        return {
            ObjectAction.EXPLAIN: WorkflowType.EXPLANATION,
            ObjectAction.VISUALIZE: WorkflowType.VISUALIZATION,
            ObjectAction.IMPLEMENT: WorkflowType.IMPLEMENTATION,
            ObjectAction.SHOW_RELATIONS: WorkflowType.PREREQUISITE,
        }
