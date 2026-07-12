from dataclasses import dataclass

from frontend.src.workspace import (

    ResearchWorkspace,

    WorkspaceEventType,

    WorkspaceRegion,
)

from backend.interaction import (

    InteractionHistory,

    ObjectAction,

    ResearchObject,

    ResearchObjectType,
)

from frontend.src.timeline import (
    TimelineStepStatus,
)

from backend.session import (

    ResearchArtifact,

    ResearchArtifactType,
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


def test_workspace_tracks_object_navigation():

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

    breadcrumbs = (

        workspace.breadcrumb_items()
    )

    assert (

        breadcrumbs[-1].label

        == "Attention"
    )

    assert (

        breadcrumbs[-1].context_type

        == "concept"
    )


def test_workspace_tracks_learning_timeline():

    workspace = (
        ResearchWorkspace()
    )

    workspace.load_workflow_timeline(

        [

            "Explain",

            "Visualize",

            "Quiz",
        ]
    )

    workspace.activate_workflow_step(

        "step-1"
    )

    steps = (

        workspace
        .workflow_timeline_steps()
    )

    assert (

        len(steps)

        == 3
    )

    assert (

        steps[0].status

        == TimelineStepStatus.ACTIVE
    )


def test_workspace_switches_to_learning_view():

    workspace = (
        ResearchWorkspace()
    )

    workspace.show_learning_content()

    assert (

        workspace.state.active_view

        == "learning"
    )


def test_workspace_loads_interaction_history():

    class Session:

        interaction_history = (
            InteractionHistory()
        )

    Session.interaction_history.record(

        "attention",

        "Attention",

        ObjectAction.EXPLAIN,
    )

    workspace = (
        ResearchWorkspace()
    )

    model = (

        workspace.load_interaction_history(

            Session()
        )
    )

    assert (

        len(model.entries)

        == 1
    )

    assert (

        model.entries[0].object_title

        == "Attention"
    )


def test_workspace_loads_next_action_recommendations():

    class Recommendation:

        id = "visualize-attention"

        title = "Visualize Attention"

        description = (
            "See the mechanism visually."
        )

        action = "visualize"

        object_id = "attention"

        priority = 10

    workspace = (
        ResearchWorkspace()
    )

    model = (

        workspace.load_recommendations(

            [
                Recommendation(),
            ]
        )
    )

    assert (

        len(model.recommendations)

        == 1
    )

    assert (

        model.recommendations[0].action

        == "visualize"
    )


def test_workspace_records_state_transitions():

    workspace = (
        ResearchWorkspace()
    )

    workspace.show_knowledge_graph()

    events = (

        workspace.workspace_events()
    )

    assert (

        events[-1].event_type

        == WorkspaceEventType.VIEW_CHANGED
    )

    assert (

        events[-1].payload

        == "knowledge_graph"
    )


def test_workspace_restores_learning_artifact():

    workspace = (
        ResearchWorkspace()
    )

    artifact = ResearchArtifact(

        session_id="session-1",

        object_id="attention",

        artifact_type=(

            ResearchArtifactType
            .EXPLANATION
        ),

        action="explain",

        content="Historical explanation",
    )

    content = (

        workspace
        .restore_learning_artifact(

            artifact
        )
    )

    assert (

        content.body

        == "Historical explanation"
    )

    assert (

        content.metadata[
            "restored"
        ]

        is True
    )
