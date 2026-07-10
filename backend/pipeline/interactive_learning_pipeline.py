from backend.session import (
    QuestionManager,
    ContextRetriever,
    ContextManager,
    RetrievedContext,
)

from backend.tutor import (
    RuleBasedTutor,
    TutorResponse,
    LearningGapAnalyzer,
    AdaptiveRecommendationEngine,
)

from backend.workflows import (
    LearningIntentDetector,
    LearningWorkflowRouter,
    LearningWorkflowPlanner,
    WorkflowExecutionResult,
)

from backend.interaction import (
    ConceptActionEngine,
    EquationActionEngine,
    FigureActionEngine,
    ExperimentActionEngine,
)


class InteractiveLearningPipeline:
    """
    Orchestrates the complete tutoring workflow
    for a learner session.
    """

    def __init__(self):

        self.question_manager = QuestionManager()

        self.context_retriever = ContextRetriever()

        self.context_manager = ContextManager()

        self.tutor = RuleBasedTutor()

        self.gap_analyzer = LearningGapAnalyzer()

        self.recommendation_engine = (
            AdaptiveRecommendationEngine()
        )

        self.intent_detector = (
            LearningIntentDetector()
        )

        self.workflow_router = (
            LearningWorkflowRouter()
        )

        self.workflow_planner = (
            LearningWorkflowPlanner()
        )

        self.concept_actions = (
            ConceptActionEngine(
                self.workflow_router,
            )
        )

        self.equation_actions = (
            EquationActionEngine(
                self.workflow_router,
            )
        )

        self.figure_actions = (
            FigureActionEngine(
                self.workflow_router,
            )
        )

        self.experiment_actions = (
            ExperimentActionEngine(
                self.workflow_router,
            )
        )

    def execute_experiment_action(

        self,

        research_object,

        action,

        session,

        paper,

    ):

        return (

            self.experiment_actions.execute(

                research_object,

                action,

                session,

                paper,
            )
        )

    def execute_figure_action(

        self,

        research_object,

        action,

        session,

        paper,

    ):

        return (

            self.figure_actions.execute(

                research_object,

                action,

                session,

                paper,
            )
        )

    def execute_equation_action(

        self,

        research_object,

        action,

        session,

        paper,

    ):

        return (

            self.equation_actions.execute(

                research_object,

                action,

                session,

                paper,
            )
        )

    def execute_concept_action(

        self,

        research_object,

        action,

        session,

        paper,

    ):

        return (

            self.concept_actions.execute(

                research_object,

                action,

                session,

                paper,
            )
        )

    def answer(

        self,

        session,

        paper,

        question,

        mode,

        topic=None,

    ):

        intent = self.intent_detector.detect(
            question,
        )

        plan = (

            self.workflow_planner.create_plan(

                intent,
            )
        )

        workflow = plan.workflows[0]

        learning_question = (

            self.question_manager.ask(

                session,

                question,

                topic,

                mode,

                intent,

                workflow,
            )
        )

        result = WorkflowExecutionResult()

        if paper is not None:

            for planned_workflow in plan.workflows:

                try:

                    response = (

                        self.workflow_router.execute(

                            planned_workflow,

                            session,

                            paper,

                            question,
                        )
                    )

                except NotImplementedError:

                    response = None

                if response is None:

                    context = (

                        self.context_retriever.retrieve(

                            paper,

                            question,
                        )
                    )

                    self.context_manager.update(

                        session,

                        context,
                    )

                    response = self.tutor.answer(

                        session,

                        paper,

                        context,

                        question,

                        mode,
                    )

                result.responses.append(
                    response,
                )

                result.executed_workflows.append(
                    planned_workflow.value,
                )

                session.workflow_memory.add(

                    planned_workflow,

                    session.active_concept
                    or "Unknown",
                )

        else:

            context = RetrievedContext(
                concepts=[],
                sections=[],
                equations=[],
            )

            self.context_manager.update(

                session,

                context,
            )

            result.responses.append(

                TutorResponse(
                    answer="No paper is attached to this session yet.",
                    confidence=0.0,
                )
            )

        self.gap_analyzer.analyze(
            session,
        )

        self.recommendation_engine.recommend(
            session,
        )

        return {

            "question": learning_question,

            "workflow_plan":
                result.executed_workflows,

            "responses":
                result.responses,

            "recommendations":
                session.recommendations,
        }
