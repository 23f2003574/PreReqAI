from backend.models import (
    Paper,
)

from .navigation_result import (
    NavigationResult,
)


class ConceptNavigator:
    """
    Navigates through concepts extracted
    from a research paper.
    """

    def navigate(

        self,

        paper: Paper,

        concept_name: str,

    ) -> NavigationResult:

        for concept in paper.concepts:

            if (

                concept.name.lower()

                == concept_name.lower()

            ):

                explanation = next(
                    (
                        explanation
                        for explanation in paper.concept_explanations
                        if explanation.concept.lower()
                        == concept.name.lower()
                    ),
                    None,
                )

                return NavigationResult(

                    target="concept",

                    title=concept.name,

                    summary=(
                        explanation.definition
                        if explanation
                        else "No description available for this concept."
                    ),

                    metadata={

                        "domain":
                            concept.domain,

                        "occurrences":
                            concept.occurrences,
                    },
                )

        raise ValueError(

            f"Concept '{concept_name}' "

            "not found."
        )
