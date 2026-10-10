from backend.workflows import (
    VisualizationWorkflow,
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


def test_visualization_workflow():

    workflow = (
        VisualizationWorkflow()
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

        "Visualize Multi-Head Attention",
    )

    assert response is not None
