from backend.workflows import (
    ImplementationWorkflow,
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


def test_implementation_workflow():

    workflow = (
        ImplementationWorkflow()
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

        "Show the PyTorch implementation of Attention",
    )

    assert response is not None
