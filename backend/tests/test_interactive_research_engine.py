from backend.engine import (
    InteractiveResearchEngine,
)

from backend.interaction import (
    InteractionPlan,
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


def _session():

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

    return session


def _concept():

    return ResearchObject(
        id="attention",
        object_type=(
            ResearchObjectType.CONCEPT
        ),
        title="Attention",
        description="Attention mechanism",
    )


def test_engine():

    engine = (
        InteractiveResearchEngine()
    )

    assert engine is not None


def test_engine_interact_executes_single_action():

    engine = (
        InteractiveResearchEngine()
    )

    session = _session()

    response = engine.interact(
        session,
        _concept(),
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


def test_engine_interact_many_executes_a_plan():

    engine = (
        InteractiveResearchEngine()
    )

    session = _session()

    plan = InteractionPlan(
        actions=[
            ObjectAction.EXPLAIN,
            ObjectAction.VISUALIZE,
        ],
    )

    results = engine.interact_many(
        session,
        _concept(),
        plan,
    )

    assert len(results) == 2

    assert results[0].workflow == "explanation"

    assert results[1].workflow == "visualization"

    assert (
        len(session.interaction_history.events)
        == 2
    )
