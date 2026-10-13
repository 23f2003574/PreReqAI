from backend.tutor import (
    RuleBasedTutor,
)

from backend.session import (
    LearningSession,
    RetrievedContext,
    TutorMode,
)

from backend.ingestion import (
    DocumentMetadata,
)

from backend.models import (
    Paper,
)


def test_rule_based_tutor():

    session = LearningSession()

    paper = Paper(
        source_path="paper.pdf",
        metadata=DocumentMetadata(
            title="Attention Is All You Need",
            author="Vaswani et al.",
            subject="",
            keywords="",
            creator="",
            producer="",
            page_count=15,
        ),
    )

    context = RetrievedContext(

        concepts=["Attention"],

        sections=["Method"],

        equations=[],
    )

    response = (
        RuleBasedTutor()
        .answer(

            session,

            paper,

            context,

            "Explain Attention",

            TutorMode.INTUITION,
        )
    )

    assert response.confidence == 0.0

    assert (
        "Attention"

        in response.supporting_concepts
    )


def _planned_paper():
    from backend.models.paper import LearningStep, PaperDifficulty, StudyTimeEstimate

    return Paper(
        source_path="paper.pdf",
        metadata=DocumentMetadata(
            title="T", author="A", subject="", keywords="", creator="", producer="", page_count=1,
        ),
        learning_plan=[
            LearningStep(order=2, concept="Probability", estimated_hours=3),
            LearningStep(order=1, concept="Linear Algebra", estimated_hours=4),
        ],
        study_time=StudyTimeEstimate(total_hours=7, recommended_days=2, average_hours_per_day=3.5),
        difficulty=PaperDifficulty(level="Intermediate", score=0.5, explanation="Needs algebra."),
    )


def _ask(paper, question):
    context = RetrievedContext(concepts=[], sections=[], equations=[])
    return RuleBasedTutor().answer(LearningSession(), paper, context, question, TutorMode.INTUITION)


def test_study_plan_questions_are_answered_from_the_analysis():
    paper = _planned_paper()
    plan = _ask(paper, "What should I learn before reading this paper?")
    assert plan.answer == (
        "Study these in order before the paper: 1. Linear Algebra (~4 h); 2. Probability (~3 h)."
    )
    assert plan.confidence == 0.5
    assert "7 hours" in _ask(paper, "How long will this take?").answer
    assert "Intermediate" in _ask(paper, "How difficult is it?").answer


def test_study_plan_question_without_a_plan_keeps_the_placeholder():
    paper = _planned_paper()
    paper.learning_plan = []
    response = _ask(paper, "What should I learn first?")
    assert "has not yet been configured" in response.answer and response.confidence == 0.0
