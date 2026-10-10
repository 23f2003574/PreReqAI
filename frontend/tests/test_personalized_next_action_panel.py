from dataclasses import dataclass

from backend.interaction import (
    ActionRecommendation,
    ObjectAction,
)

from frontend.src.recommendations import (
    PersonalizedNextActionPanel,
)


@dataclass
class Recommendation:

    id: str

    title: str

    description: str

    action: str

    object_id: str

    priority: int


def test_loads_personalized_recommendations():

    panel = (
        PersonalizedNextActionPanel()
    )

    recommendations = [

        Recommendation(

            id="visualize-attention",

            title="Visualize Attention",

            description=(

                "Build a visual model "
                "of the attention mechanism."
            ),

            action="visualize",

            object_id="attention",

            priority=10,
        ),

        Recommendation(

            id="quiz-attention",

            title="Test Your Understanding",

            description=(

                "Check your understanding "
                "with a short assessment."
            ),

            action="quiz",

            object_id="attention",

            priority=5,
        ),
    ]

    model = panel.load(

        recommendations
    )

    assert (

        len(model.recommendations)

        == 2
    )

    assert (

        model.recommendations[0].title

        == "Visualize Attention"
    )


def test_sorts_recommendations_by_priority():

    panel = (
        PersonalizedNextActionPanel()
    )

    recommendations = [

        Recommendation(

            id="low",

            title="Low Priority",

            description="",

            action="explain",

            object_id="attention",

            priority=1,
        ),

        Recommendation(

            id="high",

            title="High Priority",

            description="",

            action="visualize",

            object_id="attention",

            priority=10,
        ),
    ]

    model = panel.load(

        recommendations
    )

    assert (

        model.recommendations[0].id

        == "high"
    )


def test_selects_recommendation():

    panel = (
        PersonalizedNextActionPanel()
    )

    recommendations = [

        Recommendation(

            id="visualize-attention",

            title="Visualize Attention",

            description="",

            action="visualize",

            object_id="attention",

            priority=10,
        ),
    ]

    panel.load(

        recommendations
    )

    selected = panel.select(

        "visualize-attention"
    )

    assert (

        selected.action

        == "visualize"
    )

    assert (

        panel.view_model
        .selected_recommendation_id

        == "visualize-attention"
    )


def test_adapts_real_backend_recommendation_shape():

    panel = (
        PersonalizedNextActionPanel()
    )

    recommendations = [

        ActionRecommendation(

            action=ObjectAction.VISUALIZE,

            reason=(

                "Not yet completed "
                "for this object"
            ),
        ),
    ]

    model = panel.load(

        recommendations
    )

    assert (

        model.recommendations[0].action

        == "visualize"
    )

    assert (

        model.recommendations[0]
        .description

        == (

            "Not yet completed "
            "for this object"
        )
    )

    assert (

        model.recommendations[0].title

        == "Visualize"
    )
