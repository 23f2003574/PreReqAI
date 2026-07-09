from backend.navigation import (
    RelatedPaperNavigator,
)

from backend.models import (
    Paper,
    RelatedPaper,
)


def test_related_paper_navigator_finds_matching_paper():

    navigator = (
        RelatedPaperNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        related_papers=[
            RelatedPaper(
                reference_number=13,
                title="Long short-term memory",
                authors=[
                    "Sepp Hochreiter",
                    "Jurgen Schmidhuber",
                ],
                year=1997,
                relationship="cites",
                similarity_score=None,
            ),
        ],
    )

    result = navigator.navigate(
        paper,
        "long short-term memory",
    )

    assert result.target == "related_paper"
    assert result.title == "Long short-term memory"
    assert result.metadata["relationship"] == "cites"
    assert result.metadata["year"] == 1997
    assert result.metadata["similarity_score"] is None


def test_related_paper_navigator_raises_when_not_found():

    navigator = (
        RelatedPaperNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    try:
        navigator.navigate(
            paper,
            "Nonexistent Paper",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
