from .quiz_bank import (
    QUIZ_BANK,
)


class QuizGenerator:
    """
    Generates retrieval-practice questions
    from detected concepts.
    """

    def generate(
        self,
        context,
    ):

        quiz = []

        for concept in context.concepts:

            quiz.extend(

                QUIZ_BANK.get(
                    concept,
                    [],
                )
            )

        return quiz
