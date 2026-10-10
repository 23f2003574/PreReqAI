from backend.models import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
)

from frontend.src.graph import (
    KnowledgeGraphWorkspaceView,
)


def test_builds_graph_view_model():

    attention = GraphNode(

        node_id="concept:attention",

        node_type="concept",

        label="Attention",
    )

    transformer = GraphNode(

        node_id="concept:transformer",

        node_type="concept",

        label="Transformer",
    )

    graph = KnowledgeGraph(

        nodes=[

            attention,

            transformer,
        ],

        edges=[

            GraphEdge(

                source="concept:attention",

                target="concept:transformer",

                relationship="related_to",
            ),
        ],
    )

    view = (

        KnowledgeGraphWorkspaceView()
    )

    model = view.build(

        graph
    )

    assert (

        len(model.nodes)

        == 2
    )

    assert (

        len(model.edges)

        == 1
    )


def test_selects_graph_node():

    attention = GraphNode(

        node_id="concept:attention",

        node_type="concept",

        label="Attention",
    )

    graph = KnowledgeGraph(

        nodes=[
            attention,
        ]
    )

    view = (

        KnowledgeGraphWorkspaceView()
    )

    model = view.build(

        graph
    )

    selected = view.select_node(

        "concept:attention"
    )

    assert (

        selected.label

        == "Attention"
    )

    assert (

        model.selected_node_id

        == "concept:attention"
    )
