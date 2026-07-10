from backend.interaction import (
    ObjectAction,
    ReferenceActionEngine,
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


def _reference():

    return ResearchObject(
        id="vaswani2017",
        object_type=(
            ResearchObjectType.REFERENCE
        ),
        title="Attention Is All You Need",
        description="Transformer Paper",
    )


def test_reference_action_executes_real_workflow():

    engine = (
        ReferenceActionEngine()
    )

    result = engine.execute(
        _reference(),
        ObjectAction.EXPLAIN,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "explanation"

    assert result.response is not None


def test_reference_action_show_relations_runs_follow_up():

    engine = (
        ReferenceActionEngine()
    )

    result = engine.execute(
        _reference(),
        ObjectAction.SHOW_RELATIONS,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "follow_up"

    assert result.response is not None


def test_reference_action_handles_unimplemented_workflow():

    engine = (
        ReferenceActionEngine()
    )

    result = engine.execute(
        _reference(),
        ObjectAction.SHOW_PREREQUISITES,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "prerequisite"

    assert result.response is None


def test_reference_action_rejects_unsupported_action():

    engine = (
        ReferenceActionEngine()
    )

    result = engine.execute(
        _reference(),
        ObjectAction.VISUALIZE,
        LearningSession(),
        _paper(),
    )

    assert result.workflow is None

    assert result.response is None
