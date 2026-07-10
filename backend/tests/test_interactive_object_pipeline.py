from backend.pipeline import (
    InteractiveObjectPipeline,
)

from backend.interaction import (
    ObjectAction,
    ResearchObject,
    ResearchObjectType,
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


def test_pipeline():

    pipeline = (
        InteractiveObjectPipeline()
    )

    assert pipeline is not None


def test_pipeline_executes_action_and_returns_unified_response():

    pipeline = (
        InteractiveObjectPipeline()
    )

    session = LearningSession()

    session.paper = Paper(

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

    concept = ResearchObject(
        id="attention",
        object_type=(
            ResearchObjectType.CONCEPT
        ),
        title="Attention",
        description="Attention mechanism",
    )

    response = pipeline.execute(
        session,
        concept,
        ObjectAction.EXPLAIN,
    )

    assert (
        response["interaction"].workflow
        == "explanation"
    )

    assert (
        response["interaction"].response
        is not None
    )

    assert response["history_size"] == 1

    recommended_actions = [
        recommendation.action
        for recommendation
        in response["recommendations"]
    ]

    assert (
        ObjectAction.EXPLAIN
        not in recommended_actions
    )

    assert (
        ObjectAction.COMPARE
        in recommended_actions
    )
