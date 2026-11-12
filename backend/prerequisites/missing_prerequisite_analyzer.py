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
            concept.name: getattr(concept, "occurrences", None)
            for concept in paper.concepts
        }

        for prerequisite in paper.prerequisites:

            # Detected but with no usable count is missing evidence, which is not the same as the paper never mentioning it.
            detected = prerequisite.concept in mentions
            count = mentions.get(prerequisite.concept)
            count = count if isinstance(count, int) and count > 0 else (None if detected else 0)

            satisfied = bool(count) and count >= COVERAGE_MIN_MENTIONS

            if count is None:
                status = "unknown"
                reason = "No mention count is available for this concept, so coverage cannot be judged; requires external study"
            elif satisfied:
                status = "covered"
            elif count:
                status = "mentioned_only"
            else:
                status = "not_mentioned"

            if count is None:
                pass
            elif satisfied:
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

                    status=status,

                    mentions=count,
                )
            )

        return paper
