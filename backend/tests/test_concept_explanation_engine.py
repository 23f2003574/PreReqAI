from backend.concepts import (
    ConceptExplanationEngine,
)

from backend.models import (
    Paper,
    DetectedConcept,
)


def test_explanation_generation():

    paper = Paper(
        source_path="sample.pdf",
        metadata=None,
    )

    paper.concepts.append(

        DetectedConcept(

            name="Softmax",

            domain="transformers",

            occurrences=2,
        )
    )

    paper = (
        ConceptExplanationEngine()
        .explain(paper)
    )

    assert len(
        paper.concept_explanations
    ) == 1
