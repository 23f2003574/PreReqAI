from backend.prerequisites import (
    DifficultyExplanationEngine,
)

from backend.models import (
    Paper,
    MissingPrerequisite,
)


def test_difficulty_explanations():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.missing_prerequisites.append(

        MissingPrerequisite(

            concept="Probability",

            satisfied=False,

            reason="Required",
        )
    )

    paper = (
        DifficultyExplanationEngine()
        .explain(paper)
    )

    assert len(
        paper.difficulty_explanations
    ) >= 1
