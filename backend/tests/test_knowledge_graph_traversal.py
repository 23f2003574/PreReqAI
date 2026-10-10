from backend.graph import (
    KnowledgeGraphTraversalEngine,
)

from backend.models import (
    KnowledgeGraph,
    GraphNode,
    GraphEdge,
)


def test_bfs_traversal():

    graph = KnowledgeGraph()

    graph.add_node(
        GraphNode(
            "A",
            "concept",
            "Transformer",
        )
    )

    graph.add_node(
        GraphNode(
            "B",
            "concept",
            "Attention",
        )
    )

    graph.add_node(
        GraphNode(
            "C",
            "concept",
            "Softmax",
        )
    )

    graph.add_edge(
        GraphEdge(
            "A",
            "B",
            "depends_on",
        )
    )

    graph.add_edge(
        GraphEdge(
            "B",
            "C",
            "depends_on",
        )
    )

    traversal = (
        KnowledgeGraphTraversalEngine()
        .breadth_first_search(
            graph,
            "A",
        )
    )

    assert traversal == [
        "A",
        "B",
        "C",
    ]
