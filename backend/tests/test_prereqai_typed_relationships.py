"""Typed knowledge-graph relationships carry the paper's own sentence; co-occurrence stays weak and nothing is invented from it."""
from types import SimpleNamespace

import pytest

from backend.graph import typed_relationships
from backend.models import GraphEdge, KnowledgeGraph

pytestmark = pytest.mark.prereqai


def _paper(sentence, concepts):
    from backend.models import Paper, Paragraph
    from backend.models.paper import DetectedConcept, DocumentMetadata

    paper = Paper(source_path="x.pdf", metadata=DocumentMetadata(title="T", author="A", subject="", keywords="", creator="", producer="", page_count=1))
    paper.paragraphs = [Paragraph(1, "1 Introduction", sentence)]
    paper.concepts = [DetectedConcept(name=n, domain="x", occurrences=2) for n in concepts]
    return paper


def test_a_cue_between_two_concepts_makes_a_typed_edge_with_its_sentence():
    found = typed_relationships.find(_paper("Graph Attention Network builds on Graph Neural Network and uses Softmax in every layer.", ["Graph Attention Network", "Graph Neural Network", "Softmax"]))
    kinds = {(a, r, b) for a, b, r, _ in found}
    assert ("Graph Attention Network", "builds_on", "Graph Neural Network") in kinds and ("Graph Neural Network", "uses", "Softmax") in kinds
    assert all(p["sentence"].startswith("Graph Attention Network builds on") for _, _, _, p in found)


def test_co_occurrence_without_a_cue_and_negated_cues_make_no_edge():
    assert typed_relationships.find(_paper("Softmax and Attention appear in the same paragraph here.", ["Softmax", "Attention"])) == []
    assert typed_relationships.find(_paper("Attention does not use Softmax in this variant.", ["Attention", "Softmax"])) == []


def test_edges_keep_their_evidence_and_the_graph_still_rejects_cycles():
    graph = KnowledgeGraph()
    graph.add_edge(GraphEdge("concept:A", "concept:B", "uses", evidence=[{"sentence": "A uses B."}]))
    graph.add_edge(GraphEdge("concept:B", "concept:A", "uses", evidence=[{"sentence": "B uses A."}]))  # a typed relationship is not a prerequisite: mutual use is allowed
    graph.add_edge(GraphEdge("concept:A", "concept:B", "depends_on"))
    with pytest.raises(ValueError):
        graph.add_edge(GraphEdge("concept:B", "concept:A", "depends_on"))


def test_dpo_graph_gains_typed_relationships_each_with_an_exact_quotation():
    from backend.prereqai_eval import gate

    paper = gate._real_papers({"dpo"})["dpo"]
    typed = [e for e in paper.knowledge_graph.edges if e.relationship not in ("co_occurs_with", "depends_on")]
    pages = {p.page_number: " ".join(p.text.split()) for p in paper.pages}
    assert len(typed) >= 5 and all(e.evidence and " ".join(e.evidence[0]["sentence"].split()) in pages[e.evidence[0]["page_number"]] for e in typed)
    assert all(e.relationship in ("co_occurs_with", "depends_on") or e.evidence for e in paper.knowledge_graph.edges)
