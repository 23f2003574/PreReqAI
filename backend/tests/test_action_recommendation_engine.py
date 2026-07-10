from backend.interaction import (
    ActionRecommendationEngine,
    ConceptActionEngine,
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


def _paper():

    return Paper(

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


def _concept():

    return ResearchObject(
        id="attention",
        object_type=(
            ResearchObjectType.CONCEPT
        ),
        title="Attention",
        description="Attention",
    )


def test_recommends_default_priority_with_no_history():

    engine = (
        ActionRecommendationEngine()
    )

    recommendations = engine.recommend(
        _concept(),
        LearningSession(),
    )

    assert len(recommendations) > 0

    assert any(

        recommendation.action
        == ObjectAction.EXPLAIN

        for recommendation
        in recommendations
    )


def test_completed_actions_are_deprioritized():

    session = LearningSession()

    ConceptActionEngine().execute(
        _concept(),
        ObjectAction.EXPLAIN,
        session,
        _paper(),
    )

    engine = (
        ActionRecommendationEngine()
    )

    recommendations = engine.recommend(
        _concept(),
        session,
    )

    recommended_actions = [
        recommendation.action
        for recommendation
        in recommendations
    ]

    assert (
        ObjectAction.EXPLAIN
        not in recommended_actions
    )

    assert (
        ObjectAction.COMPARE
        in recommended_actions
    )
