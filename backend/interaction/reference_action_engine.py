from .object_action import (
    ObjectAction,
)
from .object_action_engine import (
    ObjectActionEngine,
)


class ReferenceActionEngine(ObjectActionEngine):
    """
    Executes educational actions for
    referenced research papers.
    """

    def action_mapping(self):

        from backend.session import (
            WorkflowType,
        )

        return {
            ObjectAction.EXPLAIN: WorkflowType.EXPLANATION,
            ObjectAction.COMPARE: WorkflowType.COMPARISON,
            ObjectAction.SHOW_PREREQUISITES: WorkflowType.PREREQUISITE,
            ObjectAction.SHOW_RELATIONS: WorkflowType.FOLLOW_UP,
        }
