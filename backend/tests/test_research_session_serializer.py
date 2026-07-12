from dataclasses import dataclass

from backend.models import (
    GraphNode,
    KnowledgeGraph,
)

from backend.session import (
    ResearchSessionSerializer,
)

from frontend.src.workspace import (
    VisualResearchWorkspace,
)


@dataclass
class Section:

    id: str

    title: str

    level: int


def test_serializes_visual_workspace():

    workspace = (
        VisualResearchWorkspace()
    )

    serializer = (
        ResearchSessionSerializer()
    )

    snapshot = serializer.serialize(

        session_id="session-1",

        workspace=workspace,

        paper_id="paper-1",

        paper_title="Example Paper",
    )

    assert (

        snapshot.session_id

        == "session-1"
    )

    assert (

        snapshot.active_view

        == "paper"
    )

    assert (

        snapshot.paper_title

        == "Example Paper"
    )

    assert (

        snapshot.selected_section_id

        is None
    )

    assert (

        snapshot.selected_graph_node_id

        is None
    )


def test_serializes_selected_section_and_graph_node():

    workspace = (
        VisualResearchWorkspace()
    )

    sections = [

        Section(

            id="introduction",

            title="Introduction",

            level=1,
        ),
    ]

    attention = GraphNode(

        node_id="concept:attention",

        node_type="concept",

        label="Attention",
    )

    graph = KnowledgeGraph(

        nodes=[
            attention,
        ],
    )

    opened = workspace.open_paper(

        "Example Paper",

        sections,

        knowledge_graph=graph,
    )

    workspace.explore_section(

        opened["outline"].roots[0]
    )

    workspace.explore_graph_node(
        "concept:attention"
    )

    workspace.switch_view(
        "knowledge_graph"
    )

    serializer = (
        ResearchSessionSerializer()
    )

    snapshot = serializer.serialize(

        session_id="session-1",

        workspace=workspace,

        paper_id="paper-1",

        paper_title="Example Paper",
    )

    assert (

        snapshot.active_view

        == "knowledge_graph"
    )

    assert (

        snapshot.selected_section_id

        == "introduction"
    )

    assert (

        snapshot.selected_graph_node_id

        == "concept:attention"
    )

    assert (

        len(snapshot.breadcrumbs)

        == 3
    )

    assert (

        snapshot.metadata[
            "workspace_event_count"
        ]

        > 0
    )
