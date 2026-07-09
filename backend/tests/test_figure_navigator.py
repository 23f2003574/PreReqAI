from backend.navigation import (
    FigureNavigator,
)

from backend.models import (
    Paper,
    PaperFigure,
)


def test_figure_navigator_finds_matching_figure():

    navigator = (
        FigureNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        figures=[
            PaperFigure(
                figure_id=1,
                page_number=3,
                image_index=1,
                width=800,
                height=600,
            ),
            PaperFigure(
                figure_id=2,
                page_number=5,
                image_index=1,
                width=640,
                height=480,
            ),
        ],
    )

    result = navigator.navigate(
        paper,
        "2",
    )

    assert result.target == "figure"
    assert result.title == "Figure 2"
    assert result.metadata["page_number"] == 5
    assert result.metadata["width"] == 640


def test_figure_navigator_raises_when_not_found():

    navigator = (
        FigureNavigator()
    )

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,
    )

    try:
        navigator.navigate(
            paper,
            "9",
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
