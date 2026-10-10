from backend.workflows import (
    ComparisonWorkflow,
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


def test_comparison_workflow():

    workflow = (
        ComparisonWorkflow()
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

        "Compare Transformers and RNNs",
    )

    assert response is not None
