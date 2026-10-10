from backend.graph import (
    LearningPathGenerator,
)

from backend.models import (
    KnowledgeGraph,
    GraphNode,
    GraphEdge,
)


def test_learning_path_generation():

    graph = KnowledgeGraph()

    graph.add_node(
        GraphNode(
            "concept:Transformer",
            "concept",
            "Transformer",
        )
    )

    graph.add_node(
        GraphNode(
            "concept:Attention",
            "concept",
            "Attention",
        )
    )

    graph.add_node(
        GraphNode(
            "concept:Softmax",
            "concept",
            "Softmax",
        )
    )

    graph.add_edge(
        GraphEdge(
            "concept:Transformer",
            "concept:Attention",
            "depends_on",
        )
    )

    graph.add_edge(
        GraphEdge(
            "concept:Attention",
            "concept:Softmax",
            "depends_on",
        )
    )

    generator = LearningPathGenerator()

    path = generator.generate(
        graph,
        "Transformer",
    )

    assert path == [
        "Transformer",
        "Attention",
        "Softmax",
    ]
