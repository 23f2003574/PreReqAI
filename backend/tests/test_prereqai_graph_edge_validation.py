"""Malformed graph relationships (self-loops) are rejected; valid prerequisite chains are unchanged."""
import pytest

from backend.graph.learning_path_generator import LearningPathGenerator
from backend.models import GraphEdge, GraphNode, KnowledgeGraph


def _graph():
    graph = KnowledgeGraph()
    for name in ("Transformer", "Attention", "Softmax"):
        graph.add_node(GraphNode(node_id=f"concept:{name}", node_type="concept", label=name))
    return graph


def _edge(source, target):
    return GraphEdge(source=f"concept:{source}", target=f"concept:{target}", relationship="depends_on")


def test_self_loop_is_rejected():
    graph = _graph()
    for bad in (_edge("Attention", "Attention"),):
        with pytest.raises(ValueError):
            graph.add_edge(bad)
    assert graph.edges == []


def test_valid_prerequisite_chain_keeps_its_order():
    graph = _graph()
    graph.add_edge(_edge("Transformer", "Attention"))
    graph.add_edge(_edge("Attention", "Softmax"))
    assert LearningPathGenerator().generate(graph, "Transformer") == ["Transformer", "Attention", "Softmax"]
