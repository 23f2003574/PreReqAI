from backend.models import (
    Paper,
    MissingPrerequisite,
)


# A prerequisite counts as covered by the paper only when it is discussed, not merely named: at least this many mentions
# (bibliography excluded, as in concept detection). Fewer is "mentioned only" and the learner still studies it.
COVERAGE_MIN_MENTIONS = 3


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

        mentions = {
            concept.name: concept.occurrences
            for concept in paper.concepts
        }

        for prerequisite in paper.prerequisites:

            count = mentions.get(prerequisite.concept, 0)

            satisfied = count >= COVERAGE_MIN_MENTIONS

            if satisfied:
                reason = f"Covered within the paper ({count} mentions)"
            elif count:
                reason = (f"Mentioned {count} time{'s' if count != 1 else ''} in the paper, "
                          f"too little to count as covered; requires external study")
            else:
                reason = "Requires external study"

            paper.missing_prerequisites.append(

                MissingPrerequisite(

                    concept=prerequisite.concept,

                    satisfied=satisfied,

                    reason=reason,
                )
            )

        return paper
