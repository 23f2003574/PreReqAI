from backend.interaction import (
    ExperimentActionEngine,
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


def _experiment():

    return ResearchObject(
        id="exp1",
        object_type=(
            ResearchObjectType.EXPERIMENT
        ),
        title="Experiment 1",
        description="Evaluation on WMT14",
    )


def test_experiment_action_executes_real_workflow():

    engine = (
        ExperimentActionEngine()
    )

    result = engine.execute(
        _experiment(),
        ObjectAction.COMPARE,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "comparison"

    assert result.response is not None


def test_experiment_action_handles_unimplemented_workflow():

    engine = (
        ExperimentActionEngine()
    )

    result = engine.execute(
        _experiment(),
        ObjectAction.SHOW_RELATIONS,
        LearningSession(),
        _paper(),
    )

    assert result.workflow == "prerequisite"

    assert result.response is None


def test_experiment_action_rejects_unsupported_action():

    engine = (
        ExperimentActionEngine()
    )

    result = engine.execute(
        _experiment(),
        ObjectAction.VISUALIZE,
        LearningSession(),
        _paper(),
    )

    assert result.workflow is None

    assert result.response is None
