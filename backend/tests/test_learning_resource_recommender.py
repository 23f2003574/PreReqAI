from backend.resources import (
    LearningResourceRecommender,
)

from backend.models import (
    Paper,
    MissingPrerequisite,
)


def test_resource_recommendation():

    paper = Paper(
        source_path="paper.pdf",
        metadata=None,
    )

    paper.missing_prerequisites.append(

        MissingPrerequisite(

            concept="Linear Algebra",

            satisfied=False,

            reason="Required",
        )
    )

    paper = (
        LearningResourceRecommender()
        .recommend(paper)
    )

    assert len(
        paper.learning_resources
    ) == 1

    assert (
        paper.learning_resources[0].provider
        == "MIT OpenCourseWare"
    )
