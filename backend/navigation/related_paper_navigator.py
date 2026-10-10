from backend.models import (
    Paper,
)

from .navigation_result import (
    NavigationResult,
)


class RelatedPaperNavigator:
    """
    Navigates research papers that are
    related to the current paper.
    """

    def navigate(

        self,

        paper: Paper,

        paper_title: str,

    ) -> NavigationResult:

        query = paper_title.strip().lower()

        for related in paper.related_papers:

            if related.title.lower() == query:

                return NavigationResult(

                    target="related_paper",

                    title=related.title,

                    summary=(
                        f"Cited via reference "
                        f"[{related.reference_number}]."
                    ),

                    metadata={

                        "authors":
                            related.authors,

                        "year":
                            related.year,

                        "relationship":
                            related.relationship,

                        "similarity_score":
                            related.similarity_score,
                    },
                )

        raise ValueError(

            f"Related paper "

            f"'{paper_title}' "

            "not found."
        )
