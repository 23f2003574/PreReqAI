from backend.tutor import (
    TutorPromptBuilder,
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


def test_prompt_builder():

    builder = TutorPromptBuilder()

    session = LearningSession()

    context = RetrievedContext(

        concepts=["Attention"],

        sections=["Method"],

        equations=[],
    )

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

    prompt = builder.build(

        session,

        paper,

        context,

        "Explain Attention",

        TutorMode.INTUITION,
    )

    assert "Explain Attention" in prompt

    assert "Attention" in prompt

    assert "intuition" in prompt
