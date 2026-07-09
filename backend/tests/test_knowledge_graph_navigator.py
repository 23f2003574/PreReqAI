from backend.navigation import (
    KnowledgeGraphNavigator,
)

from backend.models import (
    Paper,
    GraphNode,
    GraphEdge,
    KnowledgeGraph,
)


def _paper_with_graph():

    graph = KnowledgeGraph(
        nodes=[
            GraphNode(
                node_id="concept:Attention",
                node_type="concept",
                label="Attention",
            ),
            GraphNode(
                node_id="concept:Softmax",
                node_type="concept",
                label="Softmax",
            ),
        ],
        edges=[
            GraphEdge(
                source="concept:Attention",
                target="concept:Softmax",
                relationship="depends_on",
            ),
        ],
    )

    return Paper(
        source_path="paper.pdf",
        metadata=None,
        knowledge_graph=graph,
    )


def test_knowledge_graph_navigator_matches_by_node_id():

    navigator = KnowledgeGraphNavigator()

    result = navigator.navigate(
        _paper_with_graph(),
        "concept:Attention",
    )

    assert result.target == "knowledge_graph"
    assert result.title == "Attention"
    assert result.metadata["outgoing_neighbors"] == [
        "concept:Softmax"
    ]
    assert result.metadata["incoming_neighbors"] == []


def test_knowledge_graph_navigator_matches_by_label():

    navigator = KnowledgeGraphNavigator()

    result = navigator.navigate(
        _paper_with_graph(),
        "softmax",
    )

    assert result.target == "knowledge_graph"
    assert result.title == "Softmax"
    assert result.metadata["incoming_neighbors"] == [
        "concept:Attention"
    ]


def test_knowledge_graph_navigator_raises_when_not_found():

    navigator = KnowledgeGraphNavigator()

    try:
        navigator.navigate(
            _paper_with_graph(),
            "Nonexistent Node",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
