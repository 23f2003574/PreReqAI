from backend.tutor import (
    TutorMode,
)

from backend.tutor.socratic_question_bank import (
    SOCRATIC_QUESTIONS,
)


def test_socratic_mode():

    assert (

        TutorMode.SOCRATIC.value

        == "socratic"
    )

    assert (

        "Transformer"

        in SOCRATIC_QUESTIONS
    )
