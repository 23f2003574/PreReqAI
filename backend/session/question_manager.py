from uuid import uuid4
from datetime import datetime, timezone

from backend.workflows import (
    LearningIntent,
)

from .learning_question import (
    LearningQuestion,
)

from .learning_session import (
    LearningSession,
)

from .tutor_mode import TutorMode


class QuestionManager:
    """
    Stores learner questions inside an
    active learning session.
    """

    def ask(

        self,

        session: LearningSession,

        question: str,

        topic: str | None = None,

        mode: TutorMode = TutorMode.INTUITION,

        intent: LearningIntent = LearningIntent.UNKNOWN,

    ) -> LearningQuestion:

        learning_question = LearningQuestion(

            question_id=str(uuid4()),

            question=question,

            topic=topic,

            timestamp=datetime.now(timezone.utc),

            mode=mode,

            intent=intent,
        )

        if topic is not None:

            session.active_concept = topic

        session.conversation_history.append(

            {
                "type": "question",
                "data": {
                    "question_id": learning_question.question_id,
                    "question": learning_question.question,
                    "topic": learning_question.topic,
                    "timestamp": learning_question.timestamp.isoformat(),
                    "answered": learning_question.answered,
                    "mode": learning_question.mode.value,
                    "intent": learning_question.intent.value,
                },
            }
        )

        return learning_question
