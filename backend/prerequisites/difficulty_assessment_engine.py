from backend.models import (
    Paper,
    PaperDifficulty,
)


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

        if missing <= 2:

            level = "Beginner"

        elif missing <= 5:

            level = "Intermediate"

        elif missing <= 8:

            level = "Advanced"

        else:

            level = "Expert"

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
