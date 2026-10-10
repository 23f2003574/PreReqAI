from backend.prerequisites import (
    PrerequisiteJustificationEngine,
)

from backend.models import (
    Paper,
    Prerequisite,
)


def test_prerequisite_justifications():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.prerequisites.append(

        Prerequisite(

            concept="Linear Algebra",

            reason="Required",

            confidence=1.0,
        )
    )

    paper = (
        PrerequisiteJustificationEngine()
        .justify(paper)
    )

    assert len(
        paper.prerequisite_justifications
    ) == 1

    assert (
        "Matrix"
        in paper.prerequisite_justifications[0]
        .justification
    )
