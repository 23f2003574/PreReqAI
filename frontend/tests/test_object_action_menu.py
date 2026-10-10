from backend.interaction import (

    ObjectAction,

    ResearchObject,

    ResearchObjectType,
)

from frontend.src.actions import (
    ObjectActionMenu,
)


class FakeInteractionEngine:

    def interact(

        self,

        session,

        research_object,

        action,

    ):

        return {

            "object":
                research_object.id,

            "action":
                action.value,
        }


def test_action_menu_builds_actions():

    menu = ObjectActionMenu(

        FakeInteractionEngine()
    )

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description="Attention mechanism",
    )

    actions = menu.build(

        research_object
    )

    assert (

        any(

            item.action

            == ObjectAction.EXPLAIN

            for item in actions
        )
    )


def test_action_menu_executes_action():

    menu = ObjectActionMenu(

        FakeInteractionEngine()
    )

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description="Attention mechanism",
    )

    result = menu.execute(

        None,

        research_object,

        ObjectAction.EXPLAIN,
    )

    assert (

        result["action"]

        == "explain"
    )
