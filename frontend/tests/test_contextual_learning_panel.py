from backend.interaction import (

    ActionExecutionResult,

    ObjectAction,

    ResearchObject,

    ResearchObjectType,
)

from backend.tutor import (
    TutorResponse,
)

from frontend.src.learning import (

    ContextualLearningPanel,

    LearningContentType,
)


def test_presents_learning_response():

    panel = (
        ContextualLearningPanel()
    )

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description="Attention mechanism",
    )

    response = {

        "interaction": {

            "workflow":
                "explanation",

            "content": (

                "Attention assigns "
                "importance to information."
            ),
        }
    }

    content = (

        panel.present_response(

            research_object,

            ObjectAction.EXPLAIN,

            response,
        )
    )

    assert (

        content.content_type

        == LearningContentType.EXPLANATION
    )

    assert (

        content.object_id

        == "attention"
    )

    assert (

        content.workflow

        == "explanation"
    )


def test_tracks_learning_content_history():

    panel = (
        ContextualLearningPanel()
    )

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description="Attention mechanism",
    )

    panel.present_response(

        research_object,

        ObjectAction.EXPLAIN,

        {

            "content":
                "Explanation",
        },
    )

    panel.present_response(

        research_object,

        ObjectAction.VISUALIZE,

        {

            "content":
                "Visualization",
        },
    )

    assert (

        len(
            panel.content_history
        )

        == 2
    )

    assert (

        panel.active_content.action

        == "visualize"
    )


def test_presents_real_backend_response_shape():

    panel = (
        ContextualLearningPanel()
    )

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description="Attention mechanism",
    )

    response = {

        "interaction": ActionExecutionResult(

            object_id="attention",

            action="explain",

            workflow="explanation",

            response=TutorResponse(

                answer=(

                    "Attention assigns "
                    "importance to information."
                ),

                confidence=0.5,
            ),
        ),

        "recommendations": [],

        "history_size": 1,
    }

    content = (

        panel.present_response(

            research_object,

            ObjectAction.EXPLAIN,

            response,
        )
    )

    assert (

        content.content_type

        == LearningContentType.EXPLANATION
    )

    assert (

        content.workflow

        == "explanation"
    )

    assert (

        content.body

        == (

            "Attention assigns "
            "importance to information."
        )
    )
