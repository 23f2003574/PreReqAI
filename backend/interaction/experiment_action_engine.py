from .object_action import (
    ObjectAction,
)
from .object_action_engine import (
    ObjectActionEngine,
)


class ExperimentActionEngine(ObjectActionEngine):
    """
    Executes educational actions for
    research experiments.
    """

    @staticmethod
    def action_mapping():

        from backend.session import (
            WorkflowType,
        )

        return {
            ObjectAction.EXPLAIN: WorkflowType.EXPLANATION,
            ObjectAction.COMPARE: WorkflowType.COMPARISON,
            ObjectAction.IMPLEMENT: WorkflowType.IMPLEMENTATION,
            ObjectAction.SHOW_RELATIONS: WorkflowType.PREREQUISITE,
        }
