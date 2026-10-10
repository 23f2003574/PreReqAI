from backend.tutor import (
    TutorMode,
)

from backend.tutor.quiz_generator import (
    QuizGenerator,
)

from backend.session import (
    RetrievedContext,
)


def test_quiz_generation():

    context = RetrievedContext(

        concepts=["Attention"],

        sections=[],

        equations=[],
    )

    quiz = (
        QuizGenerator()
        .generate(context)
    )

    assert len(
        quiz
    ) > 0

    assert (
        TutorMode.QUIZ.value
        == "quiz"
    )
