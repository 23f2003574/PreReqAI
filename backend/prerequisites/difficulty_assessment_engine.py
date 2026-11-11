from backend.models import (
    Paper,
    PaperDifficulty,
)


# Upper bound of missing prerequisite subjects for each level. The rule table has only 8 distinct prerequisite subjects, so 8 is the
# most a paper can miss; the bands 0-2, 3-4, 5-6 and 7-8 make every level reachable (the old 6-8 / "more than 8" split never produced Expert).
LEVEL_BANDS = (("Beginner", 2), ("Intermediate", 4), ("Advanced", 6))


def difficulty_level(missing: int) -> str:
    for level, upper in LEVEL_BANDS:
        if missing <= upper:
            return level
    return "Expert"


class DifficultyAssessmentEngine:
    """
    Estimates the overall difficulty of a
    research paper using prerequisite analysis.
    """

    def assess(
        self,
        paper: Paper,
    ) -> Paper:

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
