from backend.graph import (
    KnowledgeGraphQueryEngine,
)

from backend.models import (
    GraphNode,
    KnowledgeGraph,
)


def test_find_node_by_id():

    graph = KnowledgeGraph()

    graph.add_node(

        GraphNode(

            node_id="concept:Transformer",

            node_type="concept",

            label="Transformer",
        )
    )

    engine = KnowledgeGraphQueryEngine()

    node = engine.get_node(

        graph,

        "concept:Transformer",
    )

    assert node is not None

    assert node.label == "Transformer"
