from backend.interaction import (

    ResearchObject,

    ResearchObjectType,
)

from frontend.src.inspector import (
    ResearchObjectInspector,
)


def test_research_object_inspector():

    inspector = (
        ResearchObjectInspector()
    )

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description=(

            "A mechanism for weighting "
            "relevant information."
        ),

        metadata={

            "section": "3.2",

            "page": 4,
        },
    )

    view = inspector.inspect(

        research_object
    )

    assert (

        view.title

        == "Attention"
    )

    assert (

        view.object_type

        == "concept"
    )

    assert (

        len(view.fields)

        == 2
    )

    assert (

        "explain"

        in view.actions
    )
