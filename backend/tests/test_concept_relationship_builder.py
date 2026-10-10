from backend.graph import (
    ConceptRelationshipBuilder,
)

from backend.models import (
    Paper,
    DetectedConcept,
)


def test_dependency_edge_creation():

    paper = Paper(
        source_path="sample.pdf",
        metadata=None,
    )

    paper.concepts.extend([

        DetectedConcept(
            name="Multi-Head Attention",
            domain="transformers",
            occurrences=1,
        ),

        DetectedConcept(
            name="Attention",
            domain="transformers",
            occurrences=1,
        ),
    ])

    paper = ConceptRelationshipBuilder().build(
        paper,
    )

    assert len(
        paper.knowledge_graph.edges
    ) == 1
