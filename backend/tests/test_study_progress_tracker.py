from backend.progress import (
    StudyProgressTracker,
)

from backend.models import (
    Paper,
    RoadmapStep,
)


def test_progress_initialization():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.study_roadmap.append(

        RoadmapStep(

            step=1,

            concept="Linear Algebra",

            resource_title="MIT 18.06",

            provider="MIT OCW",

            estimated_hours=12,
        )
    )

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
