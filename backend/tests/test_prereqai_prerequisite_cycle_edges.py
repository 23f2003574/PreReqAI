import pytest

from backend.graph.learning_path_generator import LearningPathGenerator
from backend.models import GraphEdge, GraphNode, KnowledgeGraph


def _graph(*names):
    graph = KnowledgeGraph()
    for name in names:
        graph.add_node(GraphNode(node_id=f"concept:{name}", node_type="concept", label=name))
    return graph


def _edge(source, target, relationship="depends_on"):
    return GraphEdge(source=f"concept:{source}", target=f"concept:{target}", relationship=relationship)


def test_a_two_node_cycle_is_rejected_and_named():
    graph = _graph("A", "B")
    graph.add_edge(_edge("A", "B"))
    with pytest.raises(ValueError, match=r"prerequisite cycle: B -> A -> B"):
        graph.add_edge(_edge("B", "A"))
    assert len(graph.edges) == 1


def test_a_longer_cycle_is_rejected_and_names_every_node():
    graph = _graph("A", "B", "C")
    graph.add_edge(_edge("A", "B"))
    graph.add_edge(_edge("B", "C"))
    with pytest.raises(ValueError, match=r"prerequisite cycle: C -> A -> B -> C"):
        graph.add_edge(_edge("C", "A"))
    assert len(graph.edges) == 2


def test_an_acyclic_graph_is_accepted_and_keeps_its_path():
    graph = _graph("A", "B", "C")
    for edge in (_edge("A", "B"), _edge("B", "C"), _edge("A", "C")):  # a shortcut edge is not a cycle
        graph.add_edge(edge)
    assert len(graph.edges) == 3
    assert LearningPathGenerator().generate(graph, "A") == ["A", "B", "C"]


def test_mutual_co_occurrence_is_not_a_prerequisite_cycle():
    graph = _graph("A", "B")
    graph.add_edge(_edge("A", "B", "co_occurs_with"))
    graph.add_edge(_edge("B", "A", "co_occurs_with"))
    graph.add_edge(_edge("A", "B"))
    assert len(graph.edges) == 3
