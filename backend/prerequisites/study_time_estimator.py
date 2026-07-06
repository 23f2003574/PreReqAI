from backend.models import (
    Paper,
    StudyTimeEstimate,
)


class StudyTimeEstimator:
    """
    Estimates the study time required before
    reading a research paper.
    """

    def estimate(
        self,
        paper: Paper,
    ) -> Paper:

        total_hours = sum(

            step.estimated_hours

            for step in paper.learning_plan
        )

        recommended_days = max(
            1,
            (total_hours + 2) // 3,
        )

        paper.study_time = StudyTimeEstimate(

            total_hours=total_hours,

            recommended_days=recommended_days,

            average_hours_per_day=round(

                total_hours /

                recommended_days,

                1,
            ),
        )

        return paper
