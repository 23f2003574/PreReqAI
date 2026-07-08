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

        if paper is not None:

            response = (

                self.workflow_router.execute(

                    workflow,

                    session,

                    paper,

                    question,
                )
            )

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

            session.workflow_memory.add(

                workflow,

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

            response = TutorResponse(
                answer="No paper is attached to this session yet.",
                confidence=0.0,
            )

        self.gap_analyzer.analyze(
            session,
        )

        self.recommendation_engine.recommend(
            session,
        )

        return {

            "question": learning_question,

            "response": response,

            "recommendations":
                session.recommendations,
        }
