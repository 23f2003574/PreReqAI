from backend.models import (
    Paper,
)

from .navigation_result import (
    NavigationResult,
)


class FigureNavigator:
    """
    Navigates figures extracted from
    research papers.
    """

    def navigate(

        self,

        paper: Paper,

        figure_id: str,

    ) -> NavigationResult:

        for figure in paper.figures:

            if (

                str(figure.figure_id)

                == figure_id.strip()

            ):

                return NavigationResult(

                    target="figure",

                    title=f"Figure {figure.figure_id}",

                    summary="No caption available for this figure.",

                    metadata={

                        "page_number":
                            figure.page_number,

                        "image_index":
                            figure.image_index,

                        "width":
                            figure.width,

                        "height":
                            figure.height,
                    },
                )

        raise ValueError(

            f"Figure '{figure_id}' "

            "not found."
        )
