from backend.workflows import (
    FollowUpWorkflow,
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


def test_follow_up_workflow():

    workflow = (
        FollowUpWorkflow()
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

        "What should I study next?",
    )

    assert response is not None
