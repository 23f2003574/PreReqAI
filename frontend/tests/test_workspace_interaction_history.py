from backend.interaction import (

    InteractionHistory,

    ObjectAction,
)

from frontend.src.history import (
    WorkspaceInteractionHistory,
)


def test_builds_workspace_history():

    history = (
        InteractionHistory()
    )

    history.record(

        "attention",

        "Attention",

        ObjectAction.EXPLAIN,
    )

    history.record(

        "equation-3",

        "Equation (3)",

        ObjectAction.VISUALIZE,
    )

    workspace_history = (
        WorkspaceInteractionHistory()
    )

    model = workspace_history.load(

        history
    )

    assert (

        len(model.entries)

        == 2
    )

    assert (

        model.entries[0].object_title

        == "Attention"
    )

    assert (

        model.entries[1].action

        == "visualize"
    )


def test_selects_history_entry():

    history = (
        InteractionHistory()
    )

    history.record(

        "attention",

        "Attention",

        ObjectAction.EXPLAIN,
    )

    workspace_history = (
        WorkspaceInteractionHistory()
    )

    model = workspace_history.load(

        history
    )

    entry_id = (

        model.entries[0].id
    )

    selected = (

        workspace_history.select(

            entry_id
        )
    )

    assert (

        selected.object_id

        == "attention"
    )

    assert (

        model.selected_entry_id

        == entry_id
    )
