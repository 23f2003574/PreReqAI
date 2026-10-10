from backend.models import (
    Paper,
)

from backend.parsing import (
    ReferenceMetadataParser,
)

from .navigation_result import (
    NavigationResult,
)


class ReferenceNavigator:
    """
    Navigates bibliography references
    within research papers.
    """

    def __init__(self):

        self.metadata_parser = (
            ReferenceMetadataParser()
        )

    def navigate(

        self,

        paper: Paper,

        reference_id: str,

    ) -> NavigationResult:

        for reference in paper.references:

            if (

                str(reference.reference_number)

                == reference_id.strip()

            ):

                metadata = self.metadata_parser.parse(
                    reference.raw_text
                )

                return NavigationResult(

                    target="reference",

                    title=(
                        metadata["title"]
                        or reference.raw_text
                    ),

                    summary=reference.raw_text,

                    metadata={

                        "authors":
                            metadata["authors"],

                        "venue":
                            metadata["venue"],

                        "year":
                            metadata["year"],

                        "doi": None,
                    },
                )

        raise ValueError(

            f"Reference '{reference_id}' "

            "not found."
        )
