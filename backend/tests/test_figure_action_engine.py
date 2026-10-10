from backend.interaction import (
    FigureActionEngine,
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


def _figure():

    return ResearchObject(
        id="figure2",
        object_type=(
            ResearchObjectType.FIGURE
        ),
        title="Figure 2",
        description="Transformer Architecture",
    )


def test_figure_action_executes_real_workflow():

    engine = (
        FigureActionEngine()
    )

    result = engine.execute(
        _figure(),
        ObjectAction.EXPLAIN,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "explanation"

    assert result.response is not None


def test_figure_action_handles_unimplemented_workflow():

    engine = (
        FigureActionEngine()
    )

    result = engine.execute(
        _figure(),
        ObjectAction.SHOW_RELATIONS,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "prerequisite"

    assert result.response is None


def test_figure_action_rejects_unsupported_action():

    engine = (
        FigureActionEngine()
    )

    result = engine.execute(
        _figure(),
        ObjectAction.IMPLEMENT,
        LearningSession(),
        _paper(),
    )

    assert result.workflow is None

    assert result.response is None
