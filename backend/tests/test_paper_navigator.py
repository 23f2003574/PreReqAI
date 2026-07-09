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


def test_paper_navigator_unimplemented_target():

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
            NavigationTarget.KNOWLEDGE_GRAPH,
            "Attention",
        )
        assert False, "expected NotImplementedError"
    except NotImplementedError:
        pass
