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
    ActionRecommendationEngine,
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

        self.action_recommendations = (
            ActionRecommendationEngine()
        )

    def recommend_actions(

        self,

        research_object,

        session,

    ):

        return (

            self.action_recommendations

            .recommend(

                research_object,

                session,
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

        self._record_answer(
            session,
            learning_question,
            result.responses,
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

    @staticmethod
    def _record_answer(session, learning_question, responses):
        """Keep the session's history consistent with what the learner was told:
        the question is marked answered and its answer is stored beside it, so a
        later GET /api/session/{id} shows the whole exchange."""

        if not responses:

            return

        learning_question.answered = True

        for turn in session.conversation_history:

            if (
                turn["type"] == "question"
                and turn["data"]["question_id"] == learning_question.question_id
            ):

                turn["data"]["answered"] = True

        session.conversation_history.append(

            {
                "type": "answer",
                "data": {
                    "question_id": learning_question.question_id,
                    "answers": [
                        getattr(response, "answer", None)
                        for response in responses
                    ],
                    "supporting_concepts": sorted({
                        concept
                        for response in responses
                        for concept in getattr(response, "supporting_concepts", None) or []
                    }),
                },
            }
        )
