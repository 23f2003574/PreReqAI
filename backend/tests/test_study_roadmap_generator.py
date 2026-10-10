from backend.resources import (
    StudyRoadmapGenerator,
)

from backend.models import (
    Paper,
    LearningStep,
    LearningResource,
)


def test_study_roadmap_generation():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.learning_plan.append(

        LearningStep(

            order=1,

            concept="Linear Algebra",

            estimated_hours=12,
        )
    )

    paper.learning_resources.append(

        LearningResource(

            concept="Linear Algebra",

            title="MIT 18.06",

            provider="MIT OCW",

            url="https://example.com",

            estimated_hours=12,
        )
    )

    paper = (
        StudyRoadmapGenerator()
        .generate(paper)
    )

    assert len(
        paper.study_roadmap
    ) == 1

    assert (
        paper.study_roadmap[0].step
        == 1
    )
