from backend.progress import (
    PaperReadinessEngine,
)

from backend.models import (
    Paper,
    StudyProgress,
)


def test_readiness_evaluation():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.study_progress.extend([

        StudyProgress(
            concept="Linear Algebra",
            completed=True,
            progress_percent=100,
        ),

        StudyProgress(
            concept="Probability",
            completed=False,
            progress_percent=0,
        ),
    ])

    paper = (
        PaperReadinessEngine()
        .evaluate(paper)
    )

    assert (
        paper.readiness.progress_percent
        == 50
    )

    assert (
        paper.readiness.ready_to_read
        is False
    )
