from dataclasses import dataclass

from frontend.src.workspace import (

    ResearchWorkspace,

    WorkspaceRegion,
)

from backend.interaction import (

    ObjectAction,

    ResearchObject,

    ResearchObjectType,
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

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description="Attention mechanism",
    )

    workspace.select_object(

        research_object
    )

    assert (

        workspace.state.selected_object

        == research_object
    )


def test_default_workspace_panels():

    workspace = (
        ResearchWorkspace()
    )

    explorer_panels = (

        workspace.panels_for(

            WorkspaceRegion.EXPLORER
        )
    )

    assert (

        len(explorer_panels)

        > 0
    )

    assert (

        explorer_panels[0].id

        == "paper-explorer"
    )


def test_workspace_inspects_selected_object():

    workspace = (
        ResearchWorkspace()
    )

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description="Attention mechanism",

        metadata={

            "section": "3.2",
        },
    )

    inspector_view = (

        workspace.select_object(

            research_object
        )
    )

    assert (

        workspace.state.selected_object

        == research_object
    )

    assert (

        inspector_view.title

        == "Attention"
    )


def test_workspace_exposes_selected_object_actions():

    workspace = (
        ResearchWorkspace()
    )

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description="Attention mechanism",
    )

    workspace.select_object(

        research_object
    )

    actions = (

        workspace.available_actions()
    )

    assert (

        any(

            item.action

            == ObjectAction.EXPLAIN

            for item in actions
        )
    )


def test_workspace_loads_paper_outline():

    @dataclass
    class Section:

        id: str

        title: str

        level: int

    workspace = (
        ResearchWorkspace()
    )

    sections = [

        Section(

            id="intro",

            title="Introduction",

            level=1,
        ),

        Section(

            id="methods",

            title="Methods",

            level=1,
        ),
    ]

    outline = (

        workspace.load_paper_outline(

            "Example Paper",

            sections,
        )
    )

    assert (

        outline.paper_title

        == "Example Paper"
    )

    assert (

        len(outline.roots)

        == 2
    )


def test_workspace_switches_to_graph_view():

    workspace = (
        ResearchWorkspace()
    )

    workspace.show_knowledge_graph()

    assert (

        workspace.state.active_view

        == "knowledge_graph"
    )

    workspace.show_paper()

    assert (

        workspace.state.active_view

        == "paper"
    )
