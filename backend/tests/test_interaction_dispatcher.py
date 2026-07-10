import pytest

from backend.interaction import (
    InteractionDispatcher,
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


def test_dispatcher_routes_to_the_right_engine():

    dispatcher = (
        InteractionDispatcher()
    )

    concept = ResearchObject(
        id="attention",
        object_type=(
            ResearchObjectType.CONCEPT
        ),
        title="Attention",
        description="Attention mechanism",
    )

    result = dispatcher.dispatch(
        concept,
        ObjectAction.EXPLAIN,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "explanation"

    assert result.response is not None


def test_dispatcher_rejects_unmapped_object_type():

    dispatcher = (
        InteractionDispatcher()
    )

    section = ResearchObject(
        id="sec1",
        object_type=(
            ResearchObjectType.SECTION
        ),
        title="Introduction",
        description="Intro section",
    )

    with pytest.raises(NotImplementedError):

        dispatcher.dispatch(
            section,
            ObjectAction.EXPLAIN,
            LearningSession(),
            _paper(),
        )
