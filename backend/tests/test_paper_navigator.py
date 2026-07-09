from backend.navigation import (
    NavigationTarget,
    PaperNavigator,
)

from backend.models import (
    Paper,
    PaperSection,
)


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
