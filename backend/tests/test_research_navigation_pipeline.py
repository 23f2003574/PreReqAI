from backend.pipeline import (
    ResearchNavigationPipeline,
)

from backend.navigation import NavigationTarget

from backend.models import (
    Paper,
    PaperSection,
    Equation,
)

from backend.session import LearningSession


def test_navigation_pipeline():

    pipeline = (

        ResearchNavigationPipeline()
    )

    assert pipeline is not None


def test_pipeline_returns_navigation_history_and_recommendations():

    pipeline = ResearchNavigationPipeline()

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        sections=[
            PaperSection(
                title="Introduction",
                content="This paper studies...",
            )
        ],
    )

    session = LearningSession()

    result = pipeline.navigate(
        session,
        paper,
        NavigationTarget.SECTION,
        "Introduction",
    )

    assert result["navigation"].target == "section"
    assert result["history"] == session.navigation_history.events
    assert len(result["history"]) == 1
    assert (
        NavigationTarget.CONCEPT
        in result["recommendations"]
    )


def test_pipeline_updates_session_last_navigation():

    pipeline = ResearchNavigationPipeline()

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        equations=[
            Equation(
                equation_id=1,
                expression="softmax(QK^T)",
                section="Method",
            )
        ],
    )

    session = LearningSession()

    pipeline.navigate(
        session,
        paper,
        NavigationTarget.EQUATION,
        "1",
    )

    assert session.last_navigation is not None
    assert session.last_navigation.target == "equation"


def test_pipeline_history_grows_across_multiple_navigations():

    pipeline = ResearchNavigationPipeline()

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        sections=[
            PaperSection(
                title="Introduction",
                content="This paper studies...",
            )
        ],

        equations=[
            Equation(
                equation_id=1,
                expression="softmax(QK^T)",
                section="Method",
            )
        ],
    )

    session = LearningSession()

    pipeline.navigate(
        session,
        paper,
        NavigationTarget.SECTION,
        "Introduction",
    )

    result = pipeline.navigate(
        session,
        paper,
        NavigationTarget.EQUATION,
        "1",
    )

    assert len(result["history"]) == 2
