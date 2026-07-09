from backend.navigation import (
    SectionNavigator,
)

from backend.models import (
    Paper,
    PaperSection,
)


def test_section_navigator_finds_matching_section():

    navigator = (
        SectionNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        sections=[
            PaperSection(
                title="Introduction",
                content="This paper studies...",
            ),
            PaperSection(
                title="Method",
                content="We propose...",
            ),
        ],
    )

    result = navigator.navigate(
        paper,
        "method",
    )

    assert result.target == "section"
    assert result.title == "Method"
    assert result.summary == "We propose..."


def test_section_navigator_raises_when_not_found():

    navigator = (
        SectionNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    try:
        navigator.navigate(
            paper,
            "Conclusion",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
