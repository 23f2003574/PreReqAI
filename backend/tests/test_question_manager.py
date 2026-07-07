from backend.session import (
    SessionManager,
    QuestionManager,
)


def test_question_creation():

    session = (
        SessionManager()
        .create("Transformer")
    )

    question = (
        QuestionManager()
        .ask(

            session,

            "What is Attention?",

            "Attention",
        )
    )

    assert question.answered is False

    assert len(
        session.conversation_history
    ) == 1


def test_question_topic_updates_active_concept():

    session = (
        SessionManager()
        .create("Transformer")
    )

    QuestionManager().ask(

        session,

        "What is Attention?",

        "Attention",
    )

    assert session.active_concept == "Attention"
