from uuid import uuid4
from datetime import datetime, timezone

from .learning_question import (
    LearningQuestion,
)

from .learning_session import (
    LearningSession,
)


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

    ) -> LearningQuestion:

        learning_question = LearningQuestion(

            question_id=str(uuid4()),

            question=question,

            topic=topic,

            timestamp=datetime.now(timezone.utc),
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
                },
            }
        )

        return learning_question
