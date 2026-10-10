from .concept_action_engine import (
    ConceptActionEngine,
)
from .equation_action_engine import (
    EquationActionEngine,
)
from .experiment_action_engine import (
    ExperimentActionEngine,
)
from .figure_action_engine import (
    FigureActionEngine,
)
from .reference_action_engine import (
    ReferenceActionEngine,
)
from .research_object_type import (
    ResearchObjectType,
)


class InteractionDispatcher:
    """
    Routes interactions to the
    appropriate action engine.

    Imports backend.workflows lazily for
    the same reason ObjectActionEngine
    does: backend.models.paper already
    imports from this package, so a
    module-level import here would be
    circular.
    """

    def __init__(self, workflow_router=None):

        from backend.workflows import (
            LearningWorkflowRouter,
        )

        self.workflow_router = (
            workflow_router
            or LearningWorkflowRouter()
        )

        self.engines = {

            ResearchObjectType.CONCEPT:
                ConceptActionEngine(
                    self.workflow_router,
                ),

            ResearchObjectType.EQUATION:
                EquationActionEngine(
                    self.workflow_router,
                ),

            ResearchObjectType.FIGURE:
                FigureActionEngine(
                    self.workflow_router,
                ),

            ResearchObjectType.EXPERIMENT:
                ExperimentActionEngine(
                    self.workflow_router,
                ),

            ResearchObjectType.REFERENCE:
                ReferenceActionEngine(
                    self.workflow_router,
                ),
        }

    def dispatch(
        self,
        research_object,
        action,
        session,
        paper,
    ):

        engine = self.engines.get(
            research_object.object_type,
        )

        if engine is None:

            raise NotImplementedError(
                research_object.object_type
            )

        return engine.execute(
            research_object,
            action,
            session,
            paper,
        )
