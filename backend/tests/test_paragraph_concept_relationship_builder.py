from backend.graph import (
    ParagraphConceptRelationshipBuilder,
)

from backend.models import (
    Paper,
    Paragraph,
    DetectedConcept,
)


def test_co_occurrence_relationship():

    paper = Paper(
        source_path="sample.pdf",
        metadata=None,
    )

    paper.paragraphs.append(

        Paragraph(

            paragraph_id=1,

            section_title="Introduction",

            content="""
Transformer models use
Multi-Head Attention and
Softmax.
"""
        )
    )

    paper.concepts.extend([

        DetectedConcept(
            name="Multi-Head Attention",
            domain="transformers",
            occurrences=1,
        ),

        DetectedConcept(
            name="Softmax",
            domain="transformers",
            occurrences=1,
        ),
    ])

    paper = (
        ParagraphConceptRelationshipBuilder()
        .build(paper)
    )

    assert len(
        paper.knowledge_graph.edges
    ) == 1
