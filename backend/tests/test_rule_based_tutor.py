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
