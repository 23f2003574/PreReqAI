from backend.navigation import (
    CitationNavigator,
)

from backend.models import (
    Paper,
    Citation,
    PaperReference,
)


def test_citation_navigator_finds_matching_citation():

    navigator = (
        CitationNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        citations=[
            Citation(
                citation_id=1,
                reference_number=13,
                context="Recurrent models [13] are typically factored...",
                section="Introduction",
            ),
        ],

        references=[
            PaperReference(
                reference_number=13,
                raw_text="A. Vaswani et al. Attention is all you need.",
            ),
        ],
    )

    result = navigator.navigate(
        paper,
        "1",
    )

    assert result.target == "citation"
    assert result.title == "[13]"
    assert result.metadata["reference_number"] == 13
    assert (
        result.metadata["reference_text"]
        == "A. Vaswani et al. Attention is all you need."
    )


def test_citation_navigator_reference_text_none_when_unmatched():

    navigator = (
        CitationNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        citations=[
            Citation(
                citation_id=1,
                reference_number=99,
                context="Some context [99].",
                section="Introduction",
            ),
        ],
    )

    result = navigator.navigate(
        paper,
        "1",
    )

    assert result.metadata["reference_text"] is None


def test_citation_navigator_raises_when_not_found():

    navigator = (
        CitationNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    try:
        navigator.navigate(
            paper,
            "5",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
