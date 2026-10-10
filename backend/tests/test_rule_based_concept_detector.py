from backend.concepts import (
    RuleBasedConceptDetector,
)

from backend.models import (
    Paper,
    Paragraph,
)


def test_detects_multi_head_attention():

    paper = Paper(
        source_path="sample.pdf",
        metadata=None,
    )

    paper.paragraphs.append(
        Paragraph(
            paragraph_id=1,
            section_title="Introduction",
            content="Multi-Head Attention improves Transformer models."
        )
    )

    detector = RuleBasedConceptDetector()

    paper = detector.detect(paper)

    detected = [
        concept.name
        for concept in paper.concepts
    ]

    assert "Multi-Head Attention" in detected
