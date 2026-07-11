from frontend.src.workspace import (

    ResearchWorkspace,

    WorkspaceRegion,
)


def test_research_workspace():

    workspace = (
        ResearchWorkspace()
    )

    assert (

        WorkspaceRegion.MAIN

        in workspace.regions
    )

    assert (

        workspace.state.active_view

        == "paper"
    )


def test_workspace_object_selection():

    workspace = (
        ResearchWorkspace()
    )

    research_object = {

        "id": "attention",

        "title": "Attention",
    }

    workspace.select_object(

        research_object
    )

    assert (

        workspace.state.selected_object

        == research_object
    )
