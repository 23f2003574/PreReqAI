from backend.interaction import (
    ObjectAction,
    ResearchObject,
    ResearchObjectType,
)


def test_research_object():

    obj = ResearchObject(
        id="attention",
        object_type=(
            ResearchObjectType.CONCEPT
        ),
        title="Attention",
        description="Attention mechanism",
    )

    assert (
        obj.object_type
        == ResearchObjectType.CONCEPT
    )

    assert (
        ObjectAction.EXPLAIN.value
        == "explain"
    )


def test_available_actions_are_type_driven():

    concept = ResearchObject(
        id="attention",
        object_type=(
            ResearchObjectType.CONCEPT
        ),
        title="Attention",
        description="Attention mechanism",
    )

    equation = ResearchObject(
        id="eq-3",
        object_type=(
            ResearchObjectType.EQUATION
        ),
        title="Equation (3)",
        description="Softmax normalization",
    )

    assert (
        ObjectAction.QUIZ
        in concept.available_actions()
    )

    assert (
        ObjectAction.QUIZ
        not in equation.available_actions()
    )

    assert concept.supports(
        ObjectAction.SHOW_PREREQUISITES
    )

    assert not equation.supports(
        ObjectAction.SHOW_PREREQUISITES
    )


def test_experiment_supports_implement():

    experiment = ResearchObject(
        id="ablation-1",
        object_type=(
            ResearchObjectType.EXPERIMENT
        ),
        title="Ablation Study",
        description="Removing attention heads",
    )

    assert experiment.supports(
        ObjectAction.IMPLEMENT
    )
