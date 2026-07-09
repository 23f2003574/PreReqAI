from backend.navigation import (
    NavigationTarget,
    PaperNavigator,
)

from backend.models import (
    Paper,
)


def test_paper_navigator():

    navigator = (
        PaperNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
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
