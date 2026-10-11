"""A concept's learning path follows only depends_on edges, not paragraph co-occurrence."""
from backend.graph.knowledge_graph_traversal_engine import KnowledgeGraphTraversalEngine
from backend.graph.learning_path_generator import LearningPathGenerator
from backend.models import GraphEdge, KnowledgeGraph, GraphNode


def _graph():
    graph = KnowledgeGraph()
    for name in ("Q-Learning", "Value Function", "Transformer", "Attention"):
        graph.add_node(GraphNode(node_id=f"concept:{name}", node_type="concept", label=name))
    for source, target, relationship in (
        ("Q-Learning", "Value Function", "depends_on"),
        ("Transformer", "Attention", "depends_on"),
        ("Attention", "Q-Learning", "co_occurs_with"),
        ("Transformer", "Value Function", "co_occurs_with"),
    ):
        graph.add_edge(GraphEdge(source=f"concept:{source}", target=f"concept:{target}", relationship=relationship))
    return graph


def test_learning_path_excludes_concepts_that_only_share_a_paragraph():
    generator = LearningPathGenerator()
    assert generator.generate(_graph(), "Transformer") == ["Transformer", "Attention"]
    assert generator.generate(_graph(), "Q-Learning") == ["Q-Learning", "Value Function"]


def test_unknown_concepts_give_an_empty_path_and_unfiltered_traversal_is_unchanged():
    assert LearningPathGenerator().generate(_graph(), "Quantum Gravity") == []
    everything = KnowledgeGraphTraversalEngine().breadth_first_search(_graph(), "concept:Transformer")
    assert set(everything) == {f"concept:{n}" for n in ("Transformer", "Attention", "Q-Learning", "Value Function")}
