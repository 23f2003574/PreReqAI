from backend.models import (
    Paper,
)

from .navigation_result import (
    NavigationResult,
)


class CitationNavigator:
    """
    Navigates in-text citations within
    research papers.
    """

    def navigate(

        self,

        paper: Paper,

        citation_id: str,

    ) -> NavigationResult:

        for citation in paper.citations:

            if (

                str(citation.citation_id)

                == citation_id.strip()

            ):

                reference = next(
                    (
                        reference
                        for reference in paper.references
                        if reference.reference_number
                        == citation.reference_number
                    ),
                    None,
                )

                return NavigationResult(

                    target="citation",

                    title=f"[{citation.reference_number}]",

                    summary=citation.context,

                    metadata={

                        "section":
                            citation.section,

                        "reference_number":
                            citation.reference_number,

                        "reference_text":
                            reference.raw_text
                            if reference
                            else None,
                    },
                )

        raise ValueError(

            f"Citation '{citation_id}' "

            "not found."
        )
