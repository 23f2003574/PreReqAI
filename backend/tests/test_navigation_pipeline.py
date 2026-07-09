from backend.pipeline import NavigationPipeline

from backend.navigation import NavigationTarget

from backend.models import (
    Paper,
    PaperSection,
)

from backend.session import LearningSession


def test_navigation_pipeline_returns_navigation_and_recommendations():

    pipeline = NavigationPipeline()

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
    assert (
        NavigationTarget.CONCEPT
        in result["recommendations"]
    )
    assert len(session.navigation_history.events) == 1


def test_navigation_pipeline_recommends_based_on_second_hop():

    pipeline = NavigationPipeline()

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    session = LearningSession()

    session.navigation_history.record(
        NavigationTarget.CONCEPT,
        "Attention",
    )

    from backend.models import Equation

    paper.equations.append(
        Equation(
            equation_id=1,
            expression="softmax(QK^T)",
            section="Method",
        )
    )

    result = pipeline.navigate(
        session,
        paper,
        NavigationTarget.EQUATION,
        "1",
    )

    assert result["navigation"].target == "equation"
    assert (
        NavigationTarget.CONCEPT
        in result["recommendations"]
    )
    assert len(session.navigation_history.events) == 2
