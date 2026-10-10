from backend.prerequisites import (
    StudyTimeEstimator,
)

from backend.models import (
    Paper,
    LearningStep,
)


def test_study_time_estimation():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.learning_plan.extend([

        LearningStep(
            order=1,
            concept="Linear Algebra",
            estimated_hours=10,
        ),

        LearningStep(
            order=2,
            concept="Attention",
            estimated_hours=8,
        ),
    ])

    paper = (
        StudyTimeEstimator()
        .estimate(paper)
    )

    assert (
        paper.study_time.total_hours
        == 18
    )

    assert (
        paper.study_time.recommended_days
        == 6
    )
