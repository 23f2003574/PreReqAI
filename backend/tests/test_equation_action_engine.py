from backend.interaction import (
    EquationActionEngine,
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


def _equation():

    return ResearchObject(
        id="eq3",
        object_type=(
            ResearchObjectType.EQUATION
        ),
        title="Equation (3)",
        description="Scaled Dot Product Attention",
    )


def test_equation_action_executes_real_workflow():

    engine = (
        EquationActionEngine()
    )

    result = engine.execute(
        _equation(),
        ObjectAction.EXPLAIN,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "explanation"

    assert result.response is not None


def test_equation_action_handles_unimplemented_workflow():

    engine = (
        EquationActionEngine()
    )

    result = engine.execute(
        _equation(),
        ObjectAction.SHOW_RELATIONS,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "prerequisite"

    assert result.response is None


def test_equation_action_rejects_unsupported_action():

    engine = (
        EquationActionEngine()
    )

    result = engine.execute(
        _equation(),
        ObjectAction.QUIZ,
        LearningSession(),
        _paper(),
    )

    assert result.workflow is None

    assert result.response is None
