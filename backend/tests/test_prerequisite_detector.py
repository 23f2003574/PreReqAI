from backend.prerequisites import (
    PrerequisiteDetector,
)

from backend.models import (
    Paper,
    DetectedConcept,
)


def test_prerequisite_detection():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.concepts.append(

        DetectedConcept(

            name="Transformer",

            domain="transformers",

            occurrences=3,
        )
    )

    paper = (
        PrerequisiteDetector()
        .detect(paper)
    )

    prerequisites = {

        prerequisite.concept

        for prerequisite in paper.prerequisites
    }

    assert "Attention" in prerequisites

    assert "Neural Networks" in prerequisites
