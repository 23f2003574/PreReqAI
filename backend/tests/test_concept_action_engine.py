from backend.interaction import (
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


def test_concept_action_executes_real_workflow():

    engine = (
        ConceptActionEngine()
    )

    obj = ResearchObject(
        id="attention",
        object_type=(
            ResearchObjectType.CONCEPT
        ),
        title="Attention",
        description="Attention mechanism",
    )

    result = engine.execute(
        obj,
        ObjectAction.EXPLAIN,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "explanation"

    assert result.response is not None


def test_concept_action_handles_unimplemented_workflow():

    engine = (
        ConceptActionEngine()
    )

    obj = ResearchObject(
        id="attention",
        object_type=(
            ResearchObjectType.CONCEPT
        ),
        title="Attention",
        description="Attention mechanism",
    )

    result = engine.execute(
        obj,
        ObjectAction.QUIZ,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "quiz"

    assert result.response is None
