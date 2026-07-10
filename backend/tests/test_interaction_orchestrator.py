from backend.interaction import (
    InteractionOrchestrator,
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


def test_orchestrator():

    orchestrator = (
        InteractionOrchestrator()
    )

    assert orchestrator is not None


def test_orchestrator_executes_actions_in_order():

    orchestrator = (
        InteractionOrchestrator()
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

    plan = InteractionPlan(
        actions=[
            ObjectAction.EXPLAIN,
            ObjectAction.VISUALIZE,
            ObjectAction.QUIZ,
        ],
    )

    results = orchestrator.execute(
        session,
        concept,
        plan,
    )

    assert len(results) == 3

    assert results[0].workflow == "explanation"
    assert results[0].response is not None

    assert results[1].workflow == "visualization"
    assert results[1].response is not None

    assert results[2].workflow == "quiz"

    assert results[2].response is None

    assert (
        len(session.interaction_history.events)
        == 2
    )
