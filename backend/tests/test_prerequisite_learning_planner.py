from backend.prerequisites import (
    PrerequisiteLearningPlanner,
)

from backend.models import (
    Paper,
    MissingPrerequisite,
)


def test_learning_plan_generation():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.missing_prerequisites.extend([

        MissingPrerequisite(
            concept="Attention",
            satisfied=False,
            reason="Required",
        ),

        MissingPrerequisite(
            concept="Linear Algebra",
            satisfied=False,
            reason="Required",
        ),
    ])

    paper = (
        PrerequisiteLearningPlanner()
        .generate(paper)
    )

    assert (
        paper.learning_plan[0].concept
        == "Linear Algebra"
    )

    assert (
        paper.learning_plan[1].concept
        == "Attention"
    )
