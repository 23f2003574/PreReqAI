from backend.navigation import (
    NavigationTarget,
    PaperNavigator,
)

from backend.models import (
    Paper,
    PaperSection,
)

from backend.session import LearningSession


def test_paper_navigator():

    navigator = (
        PaperNavigator()
    )

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

    result = navigator.navigate(

        paper,

        NavigationTarget.SECTION,

        "Introduction",
    )

    assert (

        result.target

        == "section"
    )


def test_paper_navigator_raises_for_a_target_with_no_match():

    navigator = (
        PaperNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    try:
        navigator.navigate(
            paper,
            NavigationTarget.RELATED_PAPER,
            "Some Other Paper",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_paper_navigator_records_successful_navigation_to_session():

    navigator = (
        PaperNavigator()
    )

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

    navigator.navigate(
        paper,
        NavigationTarget.SECTION,
        "Introduction",
        session,
    )

    assert (
        len(session.navigation_history.events)
        == 1
    )
    assert (
        session.navigation_history.events[0].title
        == "Introduction"
    )


def test_paper_navigator_does_not_record_failed_navigation():

    navigator = (
        PaperNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    session = LearningSession()

    try:
        navigator.navigate(
            paper,
            NavigationTarget.SECTION,
            "Nonexistent Section",
            session,
        )
    except ValueError:
        pass

    assert session.navigation_history.events == []
