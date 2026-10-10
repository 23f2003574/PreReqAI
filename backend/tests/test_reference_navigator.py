from backend.navigation import (
    ReferenceNavigator,
)

from backend.models import (
    Paper,
    PaperReference,
)


def test_reference_navigator_finds_matching_reference():

    navigator = (
        ReferenceNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        references=[
            PaperReference(
                reference_number=13,
                raw_text=(
                    "Sepp Hochreiter and Jurgen Schmidhuber. "
                    "Long short-term memory. "
                    "Neural computation, 9(8):1735-1780, 1997."
                ),
            ),
        ],
    )

    result = navigator.navigate(
        paper,
        "13",
    )

    assert result.target == "reference"
    assert result.title == "Long short-term memory"
    assert result.metadata["authors"] == [
        "Sepp Hochreiter",
        "Jurgen Schmidhuber",
    ]
    assert result.metadata["year"] == 1997
    assert result.metadata["doi"] is None


def test_reference_navigator_raises_when_not_found():

    navigator = (
        ReferenceNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    try:
        navigator.navigate(
            paper,
            "99",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
