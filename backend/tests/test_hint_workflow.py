from backend.workflows import (
    HintWorkflow,
)

from backend.session import (
    LearningSession,
)

from backend.models import (
    Paper,
)

from backend.ingestion import (
    DocumentMetadata,
)


def test_hint_workflow():

    workflow = (
        HintWorkflow()
    )

    session = LearningSession()

    paper = Paper(

        source_path="paper.pdf",

        metadata=DocumentMetadata(
            title="Attention Is All You Need",
            author="",
            subject="",
            keywords="",
            creator="",
            producer="",
            page_count=1,
        ),
    )

    response = workflow.execute(

        session,

        paper,

        "Give me a hint for understanding Attention",
    )

    assert response is not None
