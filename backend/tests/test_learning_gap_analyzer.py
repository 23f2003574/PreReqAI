from backend.session import (
    LearningSession,
)

from backend.tutor import (
    LearningGapAnalyzer,
)


def test_learning_gap_analysis():

    session = LearningSession()

    session.conversation_history.append({

        "type": "quiz",

        "concept": "Attention",

        "correct": False,
    })

    gaps = (
        LearningGapAnalyzer()
        .analyze(session)
    )

    assert len(gaps) == 1

    assert gaps[0].concept == "Attention"

    assert gaps[0].mastery < 1.0
