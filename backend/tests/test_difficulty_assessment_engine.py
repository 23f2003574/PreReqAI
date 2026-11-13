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

    # six real subjects, 52 curated hours (placeholder names would count at the 5-hour fallback and rate lower)
    for name in ["Graphs", "Information Theory", "Markov Decision Process", "Attention", "Probability", "Calculus"]:

        paper.missing_prerequisites.append(

            MissingPrerequisite(

                concept=name,

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
