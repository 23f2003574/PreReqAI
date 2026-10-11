"""The knowledge graph links the reinforcement learning, diffusion, graph and Transformer concepts, not only a few attention ones."""
from backend.concepts.concept_registry import ConceptRegistry
from backend.graph.concept_relationship_builder import ConceptRelationshipBuilder
from backend.models import DetectedConcept, Paper


def _edges(*names):
    paper = Paper(source_path="p.pdf", metadata=None, pages=[], sections=[])
    paper.concepts = [DetectedConcept(name=name, domain="x", occurrences=1) for name in names]
    ConceptRelationshipBuilder().build(paper)
    return {(e.source.removeprefix("concept:"), e.target.removeprefix("concept:")) for e in paper.knowledge_graph.edges}


def test_relationships_only_reference_registry_concepts_and_never_themselves():
    known = {c.name for c in ConceptRegistry().all()}
    for source, targets in ConceptRelationshipBuilder.RELATIONSHIPS.items():
        assert source in known and set(targets) <= known and source not in targets


def test_reinforcement_learning_diffusion_and_transformer_concepts_are_linked_when_both_are_detected():
    edges = _edges("Q-Learning", "Bellman Equation", "Value Function", "Actor-Critic", "Policy Gradient",
                   "Diffusion Model", "Forward Process", "Transformer", "Positional Encoding")
    assert {("Q-Learning", "Bellman Equation"), ("Q-Learning", "Value Function"), ("Actor-Critic", "Policy Gradient"),
            ("Actor-Critic", "Value Function"), ("Diffusion Model", "Forward Process"),
            ("Transformer", "Positional Encoding")} <= edges


def test_a_dependency_missing_from_the_paper_adds_no_edge():
    assert _edges("Q-Learning") == set()
    assert _edges("Message Passing", "Graph Neural Network") == {("Graph Neural Network", "Message Passing")}
