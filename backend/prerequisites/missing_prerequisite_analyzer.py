from backend.models import (
    Paper,
    MissingPrerequisite,
)


class MissingPrerequisiteAnalyzer:
    """
    Determines whether detected prerequisites
    are already covered within the current paper.

    This serves as the first step toward
    personalized prerequisite analysis.
    """

    def analyze(
        self,
        paper: Paper,
    ) -> Paper:

        paper.missing_prerequisites.clear()

        detected = {
            concept.name
            for concept in paper.concepts
        }

        for prerequisite in paper.prerequisites:

            satisfied = (
                prerequisite.concept
                in detected
            )

            paper.missing_prerequisites.append(

                MissingPrerequisite(

                    concept=prerequisite.concept,

                    satisfied=satisfied,

                    reason=(
                        "Covered within the paper"
                        if satisfied
                        else "Requires external study"
                    ),
                )
            )

        return paper
