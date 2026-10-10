from backend.prerequisites import (
    StudyActionPlanGenerator,
)

from backend.models import (
    Paper,
    LearningStep,
)


def test_action_plan_generation():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.learning_plan.append(

        LearningStep(

            order=1,

            concept="Linear Algebra",

            estimated_hours=10,
        )
    )

    paper = (
        StudyActionPlanGenerator()
        .generate(paper)
    )

    assert len(
        paper.study_actions
    ) == 1

    assert (
        paper.study_actions[0].title
        == "Study Linear Algebra"
    )
