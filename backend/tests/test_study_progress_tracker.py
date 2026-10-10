from backend.progress import (
    StudyProgressTracker,
)

from backend.models import (
    LearningStep,
    Paper,
)


def test_progress_initialization():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.learning_plan.append(LearningStep(order=1, concept="Linear Algebra", estimated_hours=12))

    paper = (
        StudyProgressTracker()
        .initialize(paper)
    )

    assert len(
        paper.study_progress
    ) == 1

    assert (
        paper.study_progress[0]
        .completed
        is False
    )
