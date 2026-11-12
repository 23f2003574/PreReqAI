from backend.models import (
    Paper,
    PaperDifficulty,
)


# Upper bound of missing prerequisite subjects for each level. The rule table has only 9 distinct prerequisite subjects (Transformer joined the 8 base ones as a prerequisite of Vision Transformer), so 9 is the
# most a paper can miss; the bands 0-2, 3-4, 5-6 and 7-9 make every level reachable (the old 6-8 / "more than 8" split never produced Expert).
LEVEL_BANDS = (("Beginner", 2), ("Intermediate", 4), ("Advanced", 6))


def difficulty_level(missing: int) -> str:
    for level, upper in LEVEL_BANDS:
        if missing <= upper:
            return level
    return "Expert"


UNKNOWN_LEVEL = "Unknown"  # no concept was detected: the paper's difficulty cannot be judged, which is not the same as easy


class DifficultyAssessmentEngine:
    """
    Estimates the overall difficulty of a
    research paper using prerequisite analysis.
    """

    def assess(
        self,
        paper: Paper,
    ) -> Paper:

        if not paper.concepts and not paper.missing_prerequisites:  # nothing was detected, so "0 missing prerequisites" says nothing about the paper

            paper.difficulty = PaperDifficulty(
                level=UNKNOWN_LEVEL,
                score=0.0,
                explanation=(
                    "Not enough evidence to rate the difficulty: no known concepts were detected in this paper "
                    "(it may be outside the supported topics, or its text could not be read)."
                ),
            )

            return paper

        missing = sum(
            1
            for prerequisite in paper.missing_prerequisites
            if not prerequisite.satisfied
        )

        level = difficulty_level(missing)

        paper.difficulty = PaperDifficulty(

            level=level,

            score=round(
                min(
                    5.0,
                    1.0 + missing * 0.4,
                ),
                1,
            ),

            explanation=(
                f"{missing} prerequisite concepts "
                "require additional study."
            ),
        )

        return paper
