from backend.graph import (
    KnowledgeGraphBuilder,
)

from backend.models import (
    Paper,
    DetectedConcept,
)


def test_graph_node_creation():

    paper = Paper(
        source_path="sample.pdf",
        metadata=None,
    )

    paper.concepts.append(

        DetectedConcept(
            name="Transformer",
            domain="transformers",
            occurrences=3,
        )
    )

    paper = KnowledgeGraphBuilder().build(
        paper,
    )

    assert len(
        paper.knowledge_graph.nodes
    ) == 1
