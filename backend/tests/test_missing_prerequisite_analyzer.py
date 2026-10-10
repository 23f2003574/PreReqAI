from backend.prerequisites import (
    MissingPrerequisiteAnalyzer,
)

from backend.models import (
    Paper,
    DetectedConcept,
    Prerequisite,
)


def test_missing_prerequisite_analysis():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.concepts.append(

        DetectedConcept(
            name="Attention",
            domain="transformers",
            occurrences=2,
        )
    )

    paper.prerequisites.append(

        Prerequisite(
            concept="Attention",
            reason="Required",
            confidence=1.0,
        )
    )

    paper.prerequisites.append(

        Prerequisite(
            concept="Linear Algebra",
            reason="Required",
            confidence=1.0,
        )
    )

    paper = (
        MissingPrerequisiteAnalyzer()
        .analyze(paper)
    )

    assert len(
        paper.missing_prerequisites
    ) == 2

    assert (
        paper.missing_prerequisites[0]
        .satisfied
        is True
    )

    assert (
        paper.missing_prerequisites[1]
        .satisfied
        is False
    )
