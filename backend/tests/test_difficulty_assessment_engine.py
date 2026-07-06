from backend.prerequisites import (
    DifficultyAssessmentEngine,
)

from backend.models import (
    Paper,
    MissingPrerequisite,
)


def test_difficulty_assessment():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    for index in range(6):

        paper.missing_prerequisites.append(

            MissingPrerequisite(

                concept=f"C{index}",

                satisfied=False,

                reason="Required",
            )
        )

    paper = (
        DifficultyAssessmentEngine()
        .assess(paper)
    )

    assert (
        paper.difficulty.level
        == "Advanced"
    )
